import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Post, Image
from .util import get_last_page, populate_helper

@click.command(name='create_tables')
@with_appcontext
def create_tables():
    db.create_all()

IC_url = 'https://geekhack.org/index.php?board=132.'
GB_url = 'https://geekhack.org/index.php?board=70.'
last_page_IC = get_last_page(IC_url)
last_page_GB = get_last_page(GB_url)

@click.command(name="populate_ic")
@with_appcontext
def populate_ic():
    populate_helper('IC', last_page_IC, IC_url)
    print("Successfully populated IC")

@click.command(name="populate_gb")
@with_appcontext
def populate_gb():
    populate_helper('GB', last_page_GB, GB_url)
    print("Successfully populated GB")

@click.command(name="populate_db")
@with_appcontext
def populate_db():
    populate_helper('IC', last_page_IC, IC_url)
    populate_helper('GB', last_page_GB, GB_url)
    print("Successfully populated IC")