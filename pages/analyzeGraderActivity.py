import streamlit as st
import pandas as pd
import numpy as np
import utils
from datetime import datetime, timedelta
from streamlit import session_state as ss

def handle_graderActivity_upload_change():
    """Callback function to update session state when canvas file is uploaded."""
    if st.session_state['graderActivity_uploader_key'] is not None:
        grader_df = pd.read_csv(st.session_state['graderActivity_uploader_key']
                                 )
        grader_df.rename(columns={'Graded time': 'Time'}, inplace=True)
        current_year = datetime.now().year - 1
        time_part = grader_df['Time'].str.extract(r'^(.*?)\s*\(')[0].str.strip()
        full_datetime_str = str(current_year) + ' ' + time_part.str.replace(" at ", " ")
        grader_df['Time'] = full_datetime_str
        grader_df['Time'] = pd.to_datetime(full_datetime_str, format='%Y %b %d %I:%M%p')
        grader_df.rename(columns={'Last graded by': 'Grader'}, inplace=True)
        
        grader_df = grader_df.sort_values(by=['Grader', 'Time'])

        # Get list of unique graders
        ss.graders = grader_df['Grader'].unique().tolist()

        ss['grader_df'] = grader_df
        calculate_statistics()
    
def handle_grader_change():
    selected_grader = ss.selected_grader
    analyze_one_grader(selected_grader)

def analyze_one_grader(grader):

    # We need to distinguish between actual breaks and time spent, for example, reading reports
    #   To do this, we use the common approach of saying breaks longer than the 95th percentile
    #   are actual breaks. This avoids problems with different types of assignments having
    #   different grading patterns, and different graders having different behaviors. Nevertheless,
    #   there needs to be an upper limit on this, because some people are taking a break after each 
    #   report. Also, our times are only saved with 1 min resolution
    temp_df = ss.grader_df[ss.grader_df['Grader'] == grader].copy()
    temp_df['pause_time'] = temp_df['Time'].diff()
    percentile_95 = min(temp_df['pause_time'].quantile(0.95), timedelta(minutes = 7.0))
    
    ss.grader_df['start'] = ss.grader_df['Time'] - percentile_95
    ss.grader_df['end'] = ss.grader_df['Time']

    oneGradersActivity_df = ss.grader_df[ss.grader_df['Grader'] == grader].copy()
    
    oneGradersActivity_df['max_end'] = oneGradersActivity_df['end'].cummax().shift().fillna(oneGradersActivity_df['start'].min())
    oneGradersActivity_df['new_group'] = oneGradersActivity_df['start'] > oneGradersActivity_df['max_end']
    oneGradersActivity_df['group_id'] = oneGradersActivity_df['new_group'].cumsum()
    
    oneGradersSessions_df = oneGradersActivity_df.groupby('group_id').agg(
        merged_start=('start', 'min'),
        merged_end=('end', 'max')
    )
    
    # Calculate duration and sum
    oneGradersSessions_df['duration'] = oneGradersSessions_df['merged_end'] - oneGradersSessions_df['merged_start']
    oneGradersSessions_df['break'] = oneGradersSessions_df['merged_end'].diff() - oneGradersSessions_df['duration']
    total_time = oneGradersSessions_df['duration'].sum().total_seconds()/3600
    numStudents =  oneGradersActivity_df['Student\'s name'].nunique()
    
    
    cols_to_drop = ['start', 'end', 'max_end', 'new_group', 'group_id']
    oneGradersActivity_df = oneGradersActivity_df.drop(columns = cols_to_drop)
    
    ss.oneGradersActivity_df = oneGradersActivity_df
    ss.oneGradersSessions_df = oneGradersSessions_df
    
    return total_time, numStudents

def calculate_statistics():
    graderSummary_df = pd.DataFrame(ss.graders, columns=['Grader'])
    
    graderSummary_df['numGraded'] = np.nan
    graderSummary_df['Time grading (hr)'] = np.nan
    graderSummary_df['Time/student (min)'] = np.nan    

    for grader in ss.graders:
        total_time, numStudents = analyze_one_grader(grader)
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'numGraded'] = numStudents
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Time grading (hr)'] = round(total_time, 2)
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Time/student (min)'] = round(60 * total_time/numStudents, 1)

    ss.graderSummary_df = graderSummary_df

def reset_uploader():
    """Function to clear the uploaded files and show the uploader again."""
    ss['grader_df'] = None

if 'grader_df' not in st.session_state:
    ss['grader_df'] = None
if 'graderSummary_df' not in ss:
    ss.graderSummary_df = pd.DataFrame()
if 'oneGradersActivity_df' not in ss:
    ss.oneGradersActivity_df = pd.DataFrame()
if 'oneGradersSessions_df' not in ss:
    ss.oneGradersSessions_df = pd.DataFrame()

st.title('Analyze Grader Activity')

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

if st.session_state['grader_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Grader Activity csv here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'graderActivity_uploader_key',
        on_change = handle_graderActivity_upload_change
    )
else:
    st.write('#### :gray[Grader activity already uploaded.]')    
    
    st.dataframe(ss.graderSummary_df)
    if len(ss.graderSummary_df) > 1:
        median_hrs = ss.graderSummary_df['Time grading (hr)'].median()
        median_min = ss.graderSummary_df['Time/student (min)'].median()
        st.write(f"Median grading time was {median_hrs} hrs or {median_min} min/student.")

    st.selectbox(
        'Select a grader', # Label for the dropdown
        options = ss.graders, # The options to display
        index = None,
        key = 'selected_grader',                # Always start at none selected
        on_change = handle_grader_change
    )

    if ss.selected_grader is not None:
        st.write('### All grader activity')
        st.dataframe(ss.oneGradersActivity_df)
        
        st.write('### All grader grading sessions')    
        st.dataframe(ss.oneGradersSessions_df)

utils.shared_sidebar()
