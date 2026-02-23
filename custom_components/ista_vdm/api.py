"""Ista VDM API Client.

A Python library for accessing the ista VDM (Verbrauchsdatenmanagement) portal.
"""

import asyncio
import csv
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
from bs4 import BeautifulSoup

from .models import ConsumptionData

__version__ = "1.0.0"

_LOGGER = logging.getLogger(__name__)

# Constants
BASE_URL = "https://ista-vdm.at"
LOGIN_URL = "https://login.ista.com/realms/vdm/protocol/openid-connect/auth"
TOKEN_URL = "https://login.ista.com/realms/vdm/protocol/openid-connect/token"


class IstaVdmAuthError(Exception):
    """Authentication error."""
    pass


class IstaVdmError(Exception):
    """General ista VDM error."""
    pass


class IstaVdmAPI:
    """API client for ista VDM."""

    def __init__(self, email: str, password: str, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the API client.
        
        Args:
            email: User email
            password: User password
            session: Optional aiohttp session
        """
        self.email = email
        self.password = password
        self._session = session
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires: Optional[float] = None
        self._flat_id: Optional[str] = None
        self._user_id: Optional[str] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def authenticate(self) -> bool:
        """Authenticate with ista VDM portal.
        
        Returns:
            True if authentication successful
            
        Raises:
            IstaVdmAuthError: If authentication fails
        """
        try:
            session = await self._get_session()
            
            # Step 1: Get the login page to extract the form action URL
            _LOGGER.debug("Step 1: Getting login page")
            params = {
                "client_id": "vdm-frontend",
                "redirect_uri": f"{BASE_URL}/login-redirect",
                "response_type": "code",
                "scope": "openid",
            }
            
            async with session.get(LOGIN_URL, params=params, allow_redirects=True) as response:
                if response.status != 200:
                    raise IstaVdmAuthError(f"Failed to load login page: {response.status}")
                
                login_page = await response.text()
                soup = BeautifulSoup(login_page, 'html.parser')
                
                # Find the form action (try multiple possible form IDs)
                form = soup.find('form', {'id': 'kc-form-login'}) or soup.find('form', {'id': 'loginForm'})
                if not form:
                    # Try finding any form with username/password fields
                    forms = soup.find_all('form')
                    for f in forms:
                        username_input = f.find('input', {'name': 'username'}) or f.find('input', {'id': 'username'})
                        password_input = f.find('input', {'name': 'password'}) or f.find('input', {'id': 'password'})
                        if username_input and password_input:
                            form = f
                            break
                    
                    if not form:
                        raise IstaVdmAuthError("Login form not found on page")
                
                form_action = form.get('action')
                if not form_action:
                    raise IstaVdmAuthError("Form action not found")
                
                _LOGGER.debug(f"Form action: {form_action}")
            
            # Step 2: Submit login credentials
            _LOGGER.debug("Step 2: Submitting credentials")
            login_data = {
                "username": self.email,
                "password": self.password,
            }
            
            async with session.post(form_action, data=login_data, allow_redirects=False) as response:
                if response.status == 200:
                    # Check for error message
                    error_page = await response.text()
                    soup = BeautifulSoup(error_page, 'html.parser')
                    error_span = soup.find('span', {'id': 'input-error'})
                    if error_span:
                        raise IstaVdmAuthError(f"Login failed: {error_span.text.strip()}")
                    raise IstaVdmAuthError("Login failed - unexpected response")
                
                if response.status not in (302, 303):
                    raise IstaVdmAuthError(f"Unexpected status code: {response.status}")
                
                # Get the redirect location (contains the authorization code)
                location = response.headers.get('Location')
                if not location:
                    raise IstaVdmAuthError("No redirect location found")
                
                _LOGGER.debug(f"Redirect location: {location}")
                
                # Extract authorization code from the redirect URL
                parsed_url = urlparse(location)
                query_params = parse_qs(parsed_url.query)
                code = query_params.get('code', [None])[0]
                
                if not code:
                    raise IstaVdmAuthError("Authorization code not found in redirect URL")
                
                _LOGGER.debug(f"Authorization code obtained")
            
            # Step 4: Exchange code for tokens
            _LOGGER.debug("Step 4: Exchanging code for tokens")
            token_data = {
                "grant_type": "authorization_code",
                "client_id": "vdm-frontend",
                "code": code,
                "redirect_uri": f"{BASE_URL}/login-redirect",
            }
            
            async with session.post(TOKEN_URL, data=token_data) as response:
                if response.status != 200:
                    raise IstaVdmAuthError(f"Failed to obtain tokens: {response.status}")
                
                token_response = await response.json()
                self._access_token = token_response.get('access_token')
                self._refresh_token = token_response.get('refresh_token')
                expires_in = token_response.get('expires_in', 300)
                self._token_expires = time.time() + expires_in
                
                if not self._access_token:
                    raise IstaVdmAuthError("Access token not received")
                
                _LOGGER.debug("Authentication successful")
            
            # Step 5: Get user and flat info
            await self._get_user_info()
            
            return True
            
        except aiohttp.ClientError as e:
            raise IstaVdmAuthError(f"Network error during authentication: {e}")
        except Exception as e:
            raise IstaVdmAuthError(f"Authentication error: {e}")

    async def _get_user_info(self):
        """Get user and flat information from the portal."""
        session = await self._get_session()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        # Get the main page to extract user info
        async with session.get(f"{BASE_URL}/api/flats", headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                _LOGGER.debug(f"Flats response: {result}")
                
                # Response is wrapped in 'data' key
                data = result.get('data', result) if isinstance(result, dict) else result
                
                if data and len(data) > 0:
                    self._flat_id = str(data[0].get('id'))
                    # Try to extract user ID from various sources
                    user_id = data[0].get('userId') or data[0].get('user_id')
                    if user_id:
                        self._user_id = str(user_id)
                    else:
                        # Fallback: try to get from token or API
                        self._user_id = await self._extract_user_id_from_profile()
                else:
                    raise IstaVdmError("No flats found for this user")
            else:
                raise IstaVdmError(f"Failed to get user info: {response.status}")
        
        _LOGGER.debug(f"Flat ID: {self._flat_id}, User ID: {self._user_id}")

    async def _extract_user_id_from_profile(self) -> Optional[str]:
        """Extract user ID from profile page or API."""
        session = await self._get_session()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        try:
            async with session.get(f"{BASE_URL}/api/user/profile", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    user_id = data.get('id') or data.get('userId') or data.get('user_id')
                    return str(user_id) if user_id else None
        except Exception as e:
            _LOGGER.debug(f"Could not get user profile: {e}")
        
        return None

    async def get_flat_info(self) -> Optional[dict]:
        """Get flat information (address, square meters, etc.).
        
        Returns:
            Dictionary with flat details or None
            
        Raises:
            IstaVdmAuthError: If authentication is required
        """
        await self._ensure_token_valid()
        
        if not self._flat_id:
            return None
        
        try:
            session = await self._get_session()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            flat_url = f"{BASE_URL}/api/flats/{self._flat_id}"
            
            async with session.get(flat_url, headers=headers) as response:
                if response.status == 401:
                    _LOGGER.warning("Token invalid (401) getting flat info, re-authenticating")
                    self._access_token = None
                    self._refresh_token = None
                    raise IstaVdmAuthError("Token expired or invalid, re-authentication required")
                if response.status == 200:
                    flat_data = await response.json()
                    data = flat_data.get('data', {})
                    
                    return {
                        'id': data.get('id'),
                        'city': data.get('city'),
                        'street': data.get('street'),
                        'housenumber': data.get('housenumber'),
                        'door': data.get('door'),
                        'squaremeter': data.get('squaremeter'),
                        'postalcode': data.get('postalcode'),
                        'flatnumber': data.get('flatnumber'),
                        'floor': data.get('floor'),
                        'property_id': data.get('property_id'),
                    }
                else:
                    _LOGGER.warning(f"Failed to get flat info: {response.status}")
                    return None
        except IstaVdmAuthError:
            raise
        except Exception as e:
            _LOGGER.error(f"Error getting flat info: {e}")
            return None

    async def _ensure_token_valid(self):
        """Ensure access token is valid, refresh if needed."""
        if not self._access_token:
            await self.authenticate()
            return
        
        if self._token_expires and time.time() >= self._token_expires - 60:
            # Token is about to expire, try to refresh
            if self._refresh_token:
                await self._refresh_access_token()
            else:
                await self.authenticate()

    async def _refresh_access_token(self):
        """Refresh the access token."""
        try:
            session = await self._get_session()
            
            token_data = {
                "grant_type": "refresh_token",
                "client_id": "vdm-frontend",
                "refresh_token": self._refresh_token,
            }
            
            async with session.post(TOKEN_URL, data=token_data) as response:
                if response.status != 200:
                    # Refresh failed, re-authenticate
                    await self.authenticate()
                    return
                
                token_response = await response.json()
                self._access_token = token_response.get('access_token')
                self._refresh_token = token_response.get('refresh_token')
                expires_in = token_response.get('expires_in', 300)
                self._token_expires = time.time() + expires_in
                
                _LOGGER.debug("Token refreshed successfully")
        except Exception as e:
            _LOGGER.warning(f"Token refresh failed: {e}, re-authenticating")
            await self.authenticate()

    async def get_consumption_data(self) -> list[ConsumptionData]:
        """Get consumption data from ista VDM.
        
        Returns:
            List of ConsumptionData objects
            
        Raises:
            IstaVdmError: If data retrieval fails
            IstaVdmAuthError: If authentication is required
        """
        await self._ensure_token_valid()
        
        if not self._flat_id:
            raise IstaVdmError("Not properly authenticated - no flat ID available")
        
        try:
            session = await self._get_session()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            # Step 1: Get flat details to obtain the export URL from links
            _LOGGER.debug(f"Getting flat details for flat {self._flat_id}")
            flat_url = f"{BASE_URL}/api/flats/{self._flat_id}"
            
            async with session.get(flat_url, headers=headers) as response:
                if response.status == 401:
                    _LOGGER.warning("Token invalid (401), re-authenticating")
                    self._access_token = None
                    self._refresh_token = None
                    raise IstaVdmAuthError("Token expired or invalid, re-authentication required")
                if response.status != 200:
                    raise IstaVdmError(f"Failed to get flat details: {response.status}")
                
                flat_data = await response.json()
                _LOGGER.debug(f"Flat data: {flat_data}")
                
                # Extract export URL from links
                links = flat_data.get('links', {})
                export_url = links.get('export')
                
                if not export_url:
                    raise IstaVdmError("Export URL not found in flat details")
                
                _LOGGER.debug(f"Export URL from links: {export_url}")
            
            # Step 2: Request the export (this will redirect to the actual CSV)
            _LOGGER.debug(f"Requesting export from: {export_url}")
            
            async with session.get(export_url, headers=headers, allow_redirects=False) as response:
                if response.status == 401:
                    _LOGGER.warning("Token invalid (401) on export, re-authenticating")
                    self._access_token = None
                    self._refresh_token = None
                    raise IstaVdmAuthError("Token expired or invalid, re-authentication required")
                if response.status in (302, 303):
                    # We got redirected to the actual download URL
                    download_url = response.headers.get('Location')
                    _LOGGER.debug(f"Download URL: {download_url}")
                elif response.status == 200:
                    # Sometimes the export might be returned directly
                    download_url = export_url
                else:
                    raise IstaVdmError(f"Failed to get export: {response.status}")
            
            # Step 3: Download the CSV data
            if not download_url:
                raise IstaVdmError("Download URL not available")
            
            _LOGGER.debug(f"Downloading CSV from: {download_url}")
            async with session.get(download_url, headers=headers) as response:
                if response.status == 401:
                    _LOGGER.warning("Token invalid (401) on download, re-authenticating")
                    self._access_token = None
                    self._refresh_token = None
                    raise IstaVdmAuthError("Token expired or invalid, re-authentication required")
                if response.status != 200:
                    raise IstaVdmError(f"Failed to download CSV: {response.status}")
                
                csv_content = await response.text()
                _LOGGER.debug(f"CSV content length: {len(csv_content)}")
                _LOGGER.debug(f"CSV first 500 chars: {csv_content[:500]}")
            
            # Step 4: Parse the CSV
            return self._parse_csv(csv_content)
            
        except IstaVdmAuthError:
            raise
        except aiohttp.ClientError as e:
            raise IstaVdmError(f"Network error: {e}")
        except Exception as e:
            _LOGGER.exception(f"Error getting consumption data: {e}")
            raise IstaVdmError(f"Error getting consumption data: {e}")

    def _parse_csv(self, csv_content: str) -> list[ConsumptionData]:
        """Parse CSV content into ConsumptionData objects.
        
        Args:
            csv_content: CSV content as string
            
        Returns:
            List of ConsumptionData objects
        """
        data = []
        
        try:
            lines = csv_content.strip().splitlines()
            reader = csv.reader(lines, delimiter=';')
            
            rows = list(reader)
            _LOGGER.debug(f"CSV has {len(rows)} rows")
            
            warmwasser_data = {}
            waerme_data = {}
            
            current_section = None
            
            for i, row in enumerate(rows):
                if len(row) < 2:
                    continue
                
                row_text = row[1] if len(row) > 1 else ""
                
                if 'Warmwasser' in row_text or 'warmwasser' in row_text.lower():
                    current_section = 'warmwasser'
                    _LOGGER.debug(f"Row {i}: Found Warmwasser section")
                    continue
                elif 'Wärme' in row_text or 'waerme' in row_text.lower():
                    current_section = 'waerme'
                    _LOGGER.debug(f"Row {i}: Found Wärme section")
                    continue
                
                if current_section and len(row) >= 2:
                    month_label = row[0].strip('"=')
                    value_str = row[1].replace('"', '').replace('=', '')
                    
                    month_map = {
                        'januar': 1, 'jänner': 1, 'februar': 2, 'märz': 3, 'april': 4,
                        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
                        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
                    }
                    
                    month_label_lower = month_label.lower()
                    month_num = None
                    year = None
                    
                    for month_name, num in month_map.items():
                        if month_name in month_label_lower:
                            month_num = num
                            parts = month_label.split()
                            if len(parts) >= 2:
                                try:
                                    year = int(parts[-1])
                                except ValueError:
                                    pass
                            break
                    
                    if month_num and year:
                        try:
                            value_str_clean = value_str.replace('.', '').replace(',', '.')
                            value = float(value_str_clean)
                            
                            key = (year, month_num)
                            if current_section == 'warmwasser':
                                warmwasser_data[key] = value
                                _LOGGER.debug(f"Parsed hot water: {month_label} -> {value} m³")
                            elif current_section == 'waerme':
                                waerme_data[key] = value
                                _LOGGER.debug(f"Parsed heating: {month_label} -> {value} kWh")
                        except ValueError as e:
                            _LOGGER.warning(f"Failed to parse value '{value_str}' for {month_label}: {e}")
                    elif month_label and current_section:
                        _LOGGER.debug(f"Could not parse month/year from: {month_label}")
            
            all_months = set(warmwasser_data.keys()) | set(waerme_data.keys())
            _LOGGER.debug(f"Found {len(all_months)} months of data")
            _LOGGER.debug(f"Heating data months: {sorted(waerme_data.keys())}")
            _LOGGER.debug(f"Hot water data months: {sorted(warmwasser_data.keys())}")
            
            for year, month in sorted(all_months):
                # Calculate period dates
                period_start = date(year, month, 1)
                if month == 12:
                    period_end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = date(year, month + 1, 1) - timedelta(days=1)
                
                consumption = ConsumptionData(
                    period_start=period_start,
                    period_end=period_end,
                    heating_consumption=waerme_data.get((year, month)),
                    heating_cost=None,
                    hot_water_consumption=warmwasser_data.get((year, month)),
                    hot_water_cost=None
                )
                data.append(consumption)
            
            _LOGGER.info(f"Parsed {len(data)} consumption records")
            return data
            
        except Exception as e:
            _LOGGER.error(f"Error parsing CSV: {e}")
            raise IstaVdmError(f"Failed to parse CSV: {e}")

    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._access_token is not None

    @property
    def flat_id(self) -> Optional[str]:
        """Get the flat ID."""
        return self._flat_id

    @property
    def user_id(self) -> Optional[str]:
        """Get the user ID."""
        return self._user_id