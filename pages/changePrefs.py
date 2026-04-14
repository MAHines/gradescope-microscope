import streamlit as st
from streamlit import session_state as ss
import tomlkit
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import keyring as kr
import utils
import re
import os

def update_password_login():
    input = ss.password_login_input
    ss['toml_dict']['user']['password_login'] = input
    ss['file_dirty'] = True 

def update_use_grader_white_list():
    input = ss.use_grader_white_list_input
    ss['toml_dict']['user']['use_grader_white_list'] = input
    ss['file_dirty'] = True 

def update_grader_white_list():
    input = ss.grader_white_list_input
    st.session_state['toml_dict']['user']['grader_white_list'] = input  # Needs input validation
    st.session_state['file_dirty'] = True    

def update_archive_location():
    input = ss.archive_location_input
    if input.startswith('~/'):
        st.session_state['toml_dict']['user']['archive_location'] = input  # Needs input validation
        st.session_state['file_dirty'] = True
    else:
        st.error("Bad entry! Your location should start with ~/")    

if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'file_dirty' not in st.session_state:
    ss['file_dirty'] = False

st.markdown("# Gradescope Microscope Settings")

# Set the login method
if 'password_login_input' not in ss:
    ss.password_login_input = ss['toml_dict']['user']['password_login']

st.checkbox('Use password login?',
            key = 'password_login_input',
            on_change = update_password_login)

# Use grader white list
if 'use_grader_white_list_input' not in ss:
    ss.use_grader_white_list_input = ss['toml_dict']['user']['use_grader_white_list']

st.checkbox('Use grader white list?',
            key = 'use_grader_white_list_input',
            on_change = update_use_grader_white_list)

# Define the white list
if 'grader_white_list_input' not in ss:
    ss.grader_white_list_input = str(ss['toml_dict']['user']['grader_white_list'])

st.text_input('White listed graders GS name (e.g., Cynthia Kinsland, Melissa Hines)',
                key = 'grader_white_list_input',
                on_change = update_grader_white_list) 

if 'archive_location_input' not in ss:
    ss.archive_location_input = str(ss['toml_dict']['user']['archive_location'])

st.text_input('Archive location relative to your home directory (e.g., ~/Documents/Microscope)',
                key = 'archive_location_input',
                on_change = update_archive_location) 

if st.session_state['file_dirty']:
    st.button('Save Preferences',
               key = 'save_prefs',
               on_click = utils.write_prefs,
               type = 'primary')

utils.shared_sidebar()
