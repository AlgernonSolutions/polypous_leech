import datetime
import logging

import requests
from src.algernon import AlgObject, ajson
from src.algernon import Opossum
from requests import cookies
from retrying import retry

from src.toll_booth import CredibleCsvParser

_base_stem = 'https://www.crediblebh.com'
_url_stems = {
    'Clients': '/client/client_hipaalog.asp',
    'Employees': '/employee/emp_hipaalog.asp',
    'DataDict': '/common/hipaalog_datadict.asp',
    'ChangeDetail': '/common/hipaalog_details.asp',
    'Employee Advanced': '/employee/list_emps_adv.asp',
    'Global': '/admin/global_hipaalog.aspx',
    'Encounter': '/visit/clientvisit_view.asp',
    'Versions': "/services/lookups_service.asmx/GetVisitDocVersions",
    'ViewVersions': '/visit/clientvisit_documentation_version_view.aspx'
}


def _login_required(function):
    def wrapper(*args, **kwargs):
        driver = args[0]
        driver.credentials.refresh_if_stale(session=driver.session)
        return function(*args, **kwargs)

    return wrapper


class CredibleFrontEndLoginException(Exception):
    pass


class CredibleLoginCredentials(AlgObject):
    def __init__(self, id_source, domain_name, cookie_value, time_generated):
        self._id_source = id_source
        self._domain_name = domain_name
        self._cookie_value = cookie_value
        self._time_generated = time_generated

    @property
    def domain_name(self):
        return self._domain_name

    @property
    def cookie_value(self):
        return self._cookie_value

    @property
    def time_generated(self):
        return self._time_generated

    @property
    def as_request_cookie_jar(self):
        cookie_jar = requests.cookies.RequestsCookieJar()
        cookie_args = {
            'name': 'cbh',
            'value': self._cookie_value,
            'domain': '.crediblebh.com'
        }
        credible_cookie = requests.cookies.create_cookie(**cookie_args)
        cookie_jar.set_cookie(credible_cookie)
        return cookie_jar

    @classmethod
    def retrieve(cls, id_source, session=None, username=None, password=None, domain_name=None):
        time_generated = datetime.datetime.now()
        if not session:
            session = requests.Session()
        if not username or not password:
            credentials = Opossum.get_untrustworthy_credentials(id_source)
            username = credentials['username']
            password = credentials['password']
            domain_name = credentials['domain_name']
        attempts = 0
        while attempts < 3:
            try:
                jar = cookies.RequestsCookieJar()
                api_url = "https://login-api.crediblebh.com/api/Authenticate/CheckLogin"
                index_url = "https://ww7.crediblebh.com/index.aspx"
                first_payload = {'UserName': username,
                                 'Password': password,
                                 'DomainName': domain_name}
                headers = {'DomainName': domain_name}
                post = session.post(api_url, json=first_payload, headers=headers)
                response_json = post.json()
                session_cookie = response_json['SessionCookie']
                jar.set('SessionId', session_cookie, domain='.crediblebh.com', path='/')
                second_payload = {'SessionId': session_cookie}
                second_post = session.post(index_url, data=second_payload, cookies=jar)
                history = second_post.history
                cbh_response = history[0]
                cbh_cookies = cbh_response.cookies
                session.cookies = cbh_cookies
                cookie_values = getattr(cbh_cookies, '_cookies')
                credible_value = cookie_values['.crediblebh.com']['/']['cbh'].value
                return cls(id_source, domain_name, credible_value, time_generated)
            except KeyError or ConnectionError:
                attempts += 1
        raise CredibleFrontEndLoginException()

    @classmethod
    def parse_json(cls, json_dict):
        return cls(
            json_dict['id_source'], json_dict['domain_name'],
            json_dict['cookie_value'], json_dict['time_generated']
        )

    def is_stale(self, lifetime_minutes=30):
        cookie_age = (datetime.datetime.now() - self._time_generated).seconds
        return cookie_age >= (lifetime_minutes * 60)

    def refresh_if_stale(self, lifetime_minutes=30, **kwargs):
        if self.is_stale(lifetime_minutes):
            self.refresh(**kwargs)

    def refresh(self, session=None, username=None, password=None):
        new_credentials = self.retrieve(self._id_source, session, username, password)
        self._cookie_value = new_credentials.cookie_value

    def destroy(self, session=None):
        if not session:
            session = requests.Session()
        logout_url = 'https://ww7.crediblebh.com/secure/logout.aspx'
        session.get(
            logout_url,
            cookies=self.as_request_cookie_jar
        )


class CredibleFrontEndDriver:
    _monitor_extract_stems = {
        'Employees': '/employee/list_emps_adv.asp',
        'Clients': '/client/list_clients_adv.asp',
        'ClientVisit': '/visit/list_visits_adv.asp'
    }
    _field_value_params = {
        'Clients': 'client_id'
    }
    _field_value_maps = {
        'Date': 'datetime',
        'Service ID': 'number',
        'UTCDate': 'utc_datetime',
        'change_date': 'datetime',
        'by_emp_id': 'number'
    }

    def __init__(self, id_source, session=None, credentials=None):
        if not session:
            session = requests.Session()
        if not credentials:
            credentials = CredibleLoginCredentials.retrieve(id_source, session=session)
        self._id_source = id_source
        session.cookies = credentials.as_request_cookie_jar
        self._session = session
        self._credentials = credentials

    def __enter__(self):
        session = requests.Session()
        if not self._credentials:
            credentials = CredibleLoginCredentials.retrieve(self._id_source, session=session)
            self._credentials = credentials
        session.cookies = self._credentials.as_request_cookie_jar
        self._session = session
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._credentials.destroy(self._session)
        if exc_type:
            raise exc_val
        return True

    @property
    def credentials(self):
        return self._credentials

    @property
    def session(self):
        return self._session

    @_login_required
    def process_advanced_search(self, id_type, selected_fields, start_date=None, end_date=None):
        credible_date_format = '%m/%d/%Y'
        url = _base_stem + self._monitor_extract_stems[id_type]
        data = {
            'submitform': 'true',
            'btn_export': ' Export ',
        }
        data.update(selected_fields)
        if start_date:
            data['start_date'] = start_date.strftime(credible_date_format)
        if end_date:
            data['end_date'] = end_date.strftime(credible_date_format)
        response = self._session.post(url, data=data)
        possible_objects = CredibleCsvParser.parse_csv_response(response.text)
        return possible_objects

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
    @_login_required
    def retrieve_client_encounter(self, encounter_id):
        url = _base_stem + _url_stems['Encounter']
        response = self._session.get(url, data={'clientvisit_id': encounter_id})
        if response.status_code != 200:
            raise RuntimeError(f'could not get the encounter data for {encounter_id}, '
                               f'response code: {response.status_code}')
        return response.text

    @_login_required
    def retrieve_client_encounter_version(self, encounter_id, version_id):
        url = _base_stem + _url_stems['ViewVersions']
        data = {
            'visitdocversion_id': str(version_id),
            'clientvisit_id': str(encounter_id)
        }
        response = self._session.get(url, data=data)
        if response.status_code != 200:
            raise RuntimeError(
                f'could not get the encounter data for {encounter_id}, response code: {response.status_code}')
        return response.text

    @_login_required
    def retrieve_documentation_versions(self, encounter_id):
        url = _base_stem + _url_stems['Versions']
        response = self._session.post(url, data={'clientvisit_id': encounter_id})
        if response.status_code != 200:
            raise RuntimeError(f'could not get the version data for {encounter_id}, response code: {response.status_code}')
        return ajson.loads(response.text)['data']
