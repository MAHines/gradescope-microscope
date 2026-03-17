import streamlit as st
import pandas as pd
import tomlkit
import os
from streamlit import session_state as ss
from tomlkit import comment, document, nl, table, item
from pathlib import Path
    
def test_for_new_keys():
    """ As new preferences are added to prefs.toml, we need a way to evolve the file format
        without forcing everyone to recreate their prefs file. This function tests for the
        existence of 'new' keys, adds their default value if they are missing, then rewrites
        prefs.toml if changes have been made. 
     """
    
    start_num_keys = len(ss['toml_dict']['user'])
    
    # New keys since initial Microscope
    long_str = '[\'Cynthia Kinsland\', \'Melissa Hines\', \'Julie Laudenschlager\','
    long_str += ' \'Virginia McGhee\', \'Mike Patterson\']'
    ss['toml_dict']['user'].setdefault('use_grader_white_list', False)
    ss['toml_dict']['user'].setdefault('grader_white_list', long_str)
    
    # Rewrite prefs if necessary
    if len(ss['toml_dict']['user']) > start_num_keys: # Key added to existing pref file
        write_prefs()  

def read_prefs():

    # If the prefs file does not exist, make the default file
    prefs_file_path = Path(__file__).parent / '.streamlit' / 'prefs.toml'
    prefs_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure the parent directory exists
    long_str = '[\'Cynthia Kinsland\', \'Melissa Hines\', \'Julie Laudenschlager\','
    long_str += ' \'Virginia McGhee\', \'Mike Patterson\']'
    if not prefs_file_path.is_file():
        toml_dict = {'user': {
                        'version': '1.0',
                        'password_login': False,
                        'use_grader_white_list': True,
                        'grader_white_list': long_str
                        }
                    }
        ss['toml_dict'] = toml_dict
        write_prefs()
    else:
        with open(prefs_file_path, 'r') as fp:
            config = tomlkit.load(fp)
        
        ss['toml_dict'] = config
        
        test_for_new_keys()

def write_prefs():

    toml_dict = ss['toml_dict']
    
    # Create new TOML document object
    config = document()
    config.add(comment('This is the preferences file for Gradescope Microscope.'))
    config.add(nl())
    
    # Add key-value pairs
    config.add('user', table())
    config['user'].add('version', toml_dict['user']['version'])
    config['user']['version'].trivia.comment = '  # Version number. Currently irrelevant.'
    pwd_item = item(toml_dict['user']['password_login'])
    pwd_item.trivia.comment = '  # Use password (not SSO) login to Gradescope'
    config['user'].add('password_login', pwd_item)
    pwd_item = item(toml_dict['user']['use_grader_white_list'])
    pwd_item.trivia.comment = '  # Use grader white list to filter graders'
    config['user'].add('use_grader_white_list', pwd_item)
    config['user'].add('grader_white_list', toml_dict['user']['grader_white_list'])
    config['user']['grader_white_list'].trivia.comment = '    # White listed graders GS name (e.g., Cynthia Kinsland, Melissa Hines)'
    config.add(nl())
    
    # Dump the modified configument to a string
    prefs_file_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'prefs.toml')
    with open(prefs_file_path, 'w') as fp:
        fp.write(tomlkit.dumps(config))
    
    ss['file_dirty'] = False

def shared_sidebar():
    image_path = os.path.join(os.path.dirname(__file__), 'assets', 'Hobbes_glasses.png')
    #unique_image_path = f"{image_path}?{time.time()}"
    st.sidebar.image(image_path)
    st.sidebar.write("Melissa.Hines@cornell.edu")

