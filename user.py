from db import Db
from datetime import datetime
from time import time, sleep
from config import * 
import json, re
from requests_oauthlib import OAuth2Session
from threading import Thread

class User():
    """
    Data type for users/users of this system

    Public methods:
        * create
        * get_by_email
        * email
        * token
        * name
        * created_at
        * filter_made
        * make_filter
    """

    def __init__(self, data=None):
        if data == None:
            self._email = None
            self._token = None
            self._filter_made = None
            self._name = None
            self._created_at = None
            self._filter_id = None
        else:
            data = json.loads(data)
            self._email = data['email']
            self._token = data['token']
            self._filter_made = data['filter_made']
            self._name = data['name']
            self._created_at = datetime.fromtimestamp(data['created_at'])
            if self.token()['expires_at'] < time() + 10:
                self.refresh_token()
            self._filter_id = data['filter_id']

    def __repr__(self):
        return f"{self.email()} - {self.name()}"

    def create(self, email, name=None, token=None):
        created_at = datetime.now()
        sql = "INSERT INTO participant (email, name, token, created_at) VALUES (%s, %s, %s, %s);"
        data = [email, name, token, created_at]
        db = Db()
        try:
            db.query(sql, data)
            self._email = email
            self._name = name
            self._created_at = created_at
            self._token = token
            return True
        except Exception as e:
            print(e)
            return False


    def email(self):
        return self._email

    def token(self):
        return self._token

    def name(self):
        return self._name

    def created_at(self):
        return self._created_at

    def filter_made(self):
        return self._filter_made

    def filter_id(self):
        return self._filter_id

    def get_by_email(self, email):
        db = Db()
        sql = "SELECT * FROM participant WHERE email = %s;"
        data = [email]
        participant = db.query(sql, data)
        if participant is None:
            return None
        self._email = participant['email']
        if participant['token'] is not None:
            self._token = json.loads(participant['token'])
        else:
            self._token = None
        self._filter_made = participant['filter_made']
        self._name = participant['name']
        self._created_at = participant['created_at']
        self._filter_id = participant['filter_id']
        return self

    def json(self):
        _dict = {'email': self.email(), 'name': self.name(), 'token': self.token(), 'filter_made': self.filter_made(), 'created_at': self.created_at().timestamp(), "filter_id": self.filter_id()}
        return json.dumps(_dict)

    def make_filter(self):
        if self._email is None:
            raise Exception('No user specified: use .get_by_email() or .create() first')
        if self._token is None:
            raise Exception("User's Oauth2 token is None")

        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time()+10:
            google = self.refresh_token()
        headers = {"Content-Type": "application/json"}
        params = {
            "criteria": {
                "from": " OR ".join(whitelist)
            },
            "action": {
                "removeLabelIds": ["SPAM"],
                "addLabelIds": ["CATEGORY_PERSONAL"]
            }
        }
        r = google.post("https://www.googleapis.com/gmail/v1/users/me/settings/filters", data=json.dumps(params), headers=headers)

        if r.status_code == 200:
            filter_id = r.json()['id']
            db = Db()
            sql = "UPDATE participant SET filter_made=%s, filter_id=%s WHERE email = %s;"
            data = [True, filter_id, self.email()]
            db.query(sql, data, verbose=True)
            self._filter_made = True
            self._filter_id = filter_id 
            return True
        else:
            # TODO -- error handling
            print(r.text)
            return False

    def refresh_token(self):
        google = OAuth2Session(client_id, token=self.token())
        extra = {
            'client_id': client_id,
            'client_secret': client_secret,
        }
        self.set_token(google.refresh_token(refresh_url, **extra))
        print('token updated!')
        return google

    def user_info(self):
        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time() + 10:
            google = self.refresh_token()
        r = google.get('https://www.googleapis.com/oauth2/v1/userinfo')
        data = r.json()
        if self._name != data['name']:
            db = Db()
            sql = 'UPDATE participant SET name = %s WHERE email = %s;'
            params = [data['name'], self._email]
            db.query(sql, params)
            self._name = data['name']
        if self._email != data['email']:
            db = Db()
            sql = 'UPDATE participant SET name = %s WHERE email = %s;'
            params = [data['email'], self._email]
            db.query(sql, params)
            self._email = data['email']
        return r.json()

    def set_token(self, token):
        if self._email is None:
            raise Exception('Anonymous user, set email first')
        db = Db()
        sql = 'UPDATE participant set token = %s where email = %s;'
        data = [json.dumps(token), self.email()]
        db.query(sql, data)
        self._token = token
        return self

    def get_messages(self):
        if self.token() is None:
            raise Exception("User's Oauth2 token is None")
        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time()+10:
            google = self.refresh_token()
        r = google.get("https://www.googleapis.com/gmail/v1/users/me/messages?labelIds=CATEGORY_PROMOTIONS")
        return r.json()['messages']

    def get_message(self, message_id):
        if self.token() is None:
            raise Exception("User's Oauth2 token is None")
        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time()+10:
            google = self.refresh_token()
        try:
            r = google.get("https://www.googleapis.com/gmail/v1/users/me/messages/{}".format(message_id))
        except:
            sleep(1)
            return self.get_message(message_id)
        return r.json()

    def remove_label(self, message_id):
        if self.token() is None:
            raise Exception("User's Oauth2 token is None")
        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time()+10:
            google = self.refresh_token()
        params = {"removeLabelIds": ['CATEGORY_PROMOTIONS'], "addLabelIds": ['CATEGORY_PERSONAL']}
        headers = {"Content-Type": "application/json"}
        try:
            r = google.post("https://www.googleapis.com/gmail/v1/users/me/messages/{}/modify".format(message_id), data=json.dumps(params), headers=headers)
        except:
            sleep(1)
            r = google.post("https://www.googleapis.com/gmail/v1/users/me/messages/{}/modify".format(message_id), data=json.dumps(params), headers=headers)
        return r.text

    def _validate_message(self, message_id):
        print('new thread {}'.format(message_id))
        message = self.get_message(message_id)
        for val in message['payload']['headers']:
            if val['name'] == 'From':
                sender = val['value']
                string = re.compile("<.+@(.+)>")
                match = re.search(string, sender)
                domain = match.group(1)
                print(domain)
                for whitelisted_domain in whitelist:
                    if whitelisted_domain in domain: # gracefully handle subdomains
                        print(domain, 'removed')
                        self.remove_label(row['id'])

    def clear_promo_folder(self):
        promo_messages = self.get_messages()
        for i, row in enumerate(promo_messages):
            t = Thread(target=self._validate_message, args=(row['id'],))
            t.start()
        return True

    def go(self):
        self.clear_promo_folder()
        return self.make_filter()

    def delete_filter(self):
        if self.filter_id() is None:
            raise Exception('Filter id not defined')
        google = OAuth2Session(client_id, token=self.token())
        if self.token()['expires_at'] < time()+10:
            google = self.refresh_token()
        url = "https://www.googleapis.com/gmail/v1/users/me/settings/filters/{}".format(self.filter_id())
        print(url)
        r = google.delete(url)
        print(r.status_code)
        if str(r.status_code)[0] == '2':
            db = Db()
            sql = 'UPDATE participant set filter_made = %s, filter_id = %s where email = %s;'
            data = [False, None, self.email()]
            db.query(sql, data)
            self._filter_id = None
            self._filter_made = False
            return True
        else:
            print(r.text, r)
            return False
        

if __name__=='__main__':
    u = User()

    # get by email
    #u.get_by_email('graydenshand@gmail.com')
    #print(u.token())

    # create
    #u.create('graydenshand+test@gmail.com', 'Grayden Shand')
    #print(u)

    # to json --> from json
    #u.get_by_email('graydenshand@gmail.com')
    #string = u.json()
    #p = User(string)
    #print(p)

    # user_info 
    #u.get_by_email('graydenshand@gmail.com')
    #print(u.user_info())

    # set_token
    #token = {'access_token': 'ya29.ImCbB7-RCXlnETExBv945_682oO2VYjxCWT0lsnGCZ30FsoqZkcYH27GdkMEwXCfW7QgSKpzxf-XLgGbY-3HidpCV17dE3KTxti_EgbMZSaFLst1XzZmeIN0aym9J0tIb1c', 'expires_at': 1571326376.8499131, 'expires_in': 3600, 'id_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjNkYjNlZDZiOTU3NGVlM2ZjZDlmMTQ5ZTU5ZmYwZWVmNGY5MzIxNTMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiI1MTAyMzIyMzM3NTUtOXRldWdqNGRwODZnc2Y2NzU1MTFtZW52NWxubGJtYjkuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJhdWQiOiI1MTAyMzIyMzM3NTUtOXRldWdqNGRwODZnc2Y2NzU1MTFtZW52NWxubGJtYjkuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJzdWIiOiIxMDA0MTQ5OTU4NzM4NzI0MzUzOTQiLCJlbWFpbCI6ImdyYXlkZW5zaGFuZEBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXRfaGFzaCI6Im1BUGlVd0NvUUx4MDhuSmxwcU8wMXciLCJpYXQiOjE1NzEzMjI3NzYsImV4cCI6MTU3MTMyNjM3Nn0.zodpDP8UlpPlLPnNHRoOs6S47pPPCUYnETXbEuw64_kjkKvV-PWWhuNEBP-4kvZNT52712iIQ50VNJpeYbB2tD7Yd0R89eZwS8n7Z9YQPOjJ_o7sYJw57LSu7PEH3g3MquMLVry4Hh8Kd_uRuiqlFjjPJ5_x_HY-NshQTZf1R3bGTVnoEOHlyrJP0KQ8Xw3PiLJh_BnJo7xSKNI4ZB3Y2zTIxygzI57vOd0d-8GLOXNAObfvAtSJBIZznrF4MbWyxHSxzuVqXAeFTAHvgDQsiOHakXrWv4ZC77FVRMw7LGTUt6duhfyfub4pj6RtZIwVA6RVDm_1_m71wQOzr9FFTQ', 'refresh_token': '1/X2vsgWnYHG4Fzrfmqy_vK5azv8ZrCYqsdebWNjeqO1s', 'scope': ['https://www.googleapis.com/auth/userinfo.profile', 'openid', 'https://www.googleapis.com/auth/gmail.settings.basic', 'https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/userinfo.email'], 'token_type': 'Bearer'}
    #u.get_by_email('graydenshand@gmail.com')
    #u.set_token(token)
    #u.get_by_email('graydenshand@gmail.com')
    #print(u.token())

    # make_filter
    #u.get_by_email('graydenshand@gmail.com')
    #u.make_filter()
    #print(u.json())

    #u.get_by_email('graydenshand@gmail.com')
    #u.clear_promo_folder()

    u.get_by_email('graydenshand@gmail.com')
    print(u.json())
    print(u.delete_filter())
    print(u.make_filter())







