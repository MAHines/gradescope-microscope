import streamlit as st
import os
import keyring as kr
import utils

@st.dialog("Enter Gradescope Credentials")
def show_credentials_dialog():
    st.write("Enter username and password to be stored in system keychain:")
    
    with st.form("details_form"):
        # Two input fields
        username = st.text_input("Username (e.g., tom.smith@gmail.com)")
        password = st.text_input("Password (NOT Cornell SSO!)", type="password")
        
        # A button to submit the form within the modal
        submit_button = st.form_submit_button("Submit")

    if submit_button:
        # Store the data in system keychain, not session_state
        sysUsername = os.getlogin() # Your username on your computer (e.g., mah)
        kr.set_password('gradescope_extUsername', sysUsername, username)
        kr.set_password('gradescope_extPassword', sysUsername, password)
        st.rerun() # Rerunning the app closes the dialog programmatically

st.title('Store External Gradescope Credentials')

text_str = "This is necessary if you want to use username/password authentication (instead of SSO). "
text_str += "You can change your login type in Settings."
st.write(text_str)
if st.button("Update Gradescope Credentials",
                type = 'primary'):
    # Call the dialog function to display the modal
    show_credentials_dialog()

utils.shared_sidebar()