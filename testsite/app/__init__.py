
from flask import redirect, url_for, session
from flask.ext.security import Security, SQLAlchemyUserDatastore
from flask.ext.social import Social, SQLAlchemyConnectionDatastore, \
     login_failed
from flask.ext.social.utils import get_conection_values_from_oauth_response
from flask.ext.sqlalchemy import SQLAlchemy

from .helpers import Flask
from .middleware import MethodRewriteMiddleware
import os
import flask_gzip
import flask_social.providers.foursquare
import foursquare

def get_provider_user_id(response, **kwargs):
  if response:
    api = foursquare.Foursquare(access_token=response['access_token'])
    return api.users()['user']['id']                              
  return None
flask_social.providers.foursquare.get_provider_user_id = get_provider_user_id

app = Flask(__name__)
app.config.from_yaml(app.root_path)
app.config['DEBUG'] = True
app.wsgi_app = MethodRewriteMiddleware(app.wsgi_app)
app.secret_key = 'why would I tell you my secret key?'

flask_gzip.Gzip(app)

basedir = os.path.abspath('.')
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres@localhost:5432/gis'
db = SQLAlchemy(app)

# Late import so modules can import their dependencies properly
from . import models, views, api_routes


security_ds = SQLAlchemyUserDatastore(db, models.User, models.Role)
social_ds = SQLAlchemyConnectionDatastore(db, models.Connection)

app.security = Security(app, security_ds)
app.social = Social(app, social_ds)


class SocialLoginError(Exception):
    def __init__(self, provider):
        self.provider = provider


@app.before_first_request
def before_first_request():
    try:
        models.db.create_all()
    except Exception, e:
        app.logger.error(str(e))


@app.context_processor
def template_extras():
    return dict(
        google_analytics_id=app.config.get('GOOGLE_ANALYTICS_ID', None))


@login_failed.connect_via(app)
def on_login_failed(sender, provider, oauth_response):
    app.logger.debug('Social Login Failed via %s; '
                     '&oauth_response=%s' % (provider.name, oauth_response))

    # Save the oauth response in the session so we can make the connection
    # later after the user possibly registers
    session['failed_login_connection'] = \
        get_conection_values_from_oauth_response(provider, oauth_response)

    raise SocialLoginError(provider)


@app.errorhandler(SocialLoginError)
def social_login_error(error):
    return redirect(
        url_for('register', provider_id=error.provider.id, login_failed=1))
