import streamlit as st
import os
import utils
import time 

st.set_page_config(layout='wide')

def Home():
    # Create three columns and put content in the middle one
    left, mid, right = st.columns([1, 2, 1])
    
    with mid: #
        image_path = os.path.join(os.path.dirname(__file__), 'assets', 'Gradescope_microscope.png')
        st.image(image_path, width = 'stretch')
    utils.shared_sidebar()

pg = st.navigation({
    "": [
        st.Page(Home, title="Gradescope Microscope", default=True)
    ],
    "Scripts": [
        st.Page('pages/downloadResults.py', title='Download Gradescope Results'),
        st.Page('pages/analyzeGraderActivity.py', title='Analyze Grader Activity'),
        st.Page('pages/analyzeGradescopeFolder.py', title = 'Analyze Grades'),
        st.Page('pages/updateGradescopeCredentials.py', title='Update Gradescope Credentials'),
    ]
})

pg.run()
