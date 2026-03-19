import streamlit as st
import pandas as pd
from collections import Counter
import numpy as np
import plotly.express as px
import math
import utils
import ast
from datetime import datetime, timedelta
from streamlit import session_state as ss

def handle_grader_change():
    selected_grader = ss.selected_grader
    analyze_one_grader(selected_grader)

def analyze_one_grader(grader):
    """ Analyzes the activity of a single grader. Called repeatedly to analyze all graders. """

    # We need to distinguish between actual breaks and time spent, for example, reading reports
    #   To do this, we use the common approach of saying breaks longer than the 95th percentile
    #   are actual breaks. This avoids problems with different types of assignments having
    #   different grading patterns, and different graders having different behaviors. Nevertheless,
    #   there needs to be an upper limit on this, because some people are taking a break after each 
    #   report (fair enough). Also, our times are only saved with 1 min resolution
    temp_df = ss.grader_df[ss.grader_df['Grader'] == grader].copy()
    temp_df['pause_time'] = temp_df['Time'].diff()
    percentile_96 = min(temp_df['pause_time'].quantile(0.96), timedelta(minutes = 7.0))
    
    ss.grader_df['start'] = ss.grader_df['Time'] - percentile_96
    ss.grader_df['end'] = ss.grader_df['Time']

    oneGradersActivity_df = ss.grader_df[ss.grader_df['Grader'] == grader].copy()
    
    # This is the key bit. We convert a log of individual actions into distinct "sessions" based
    #   an gaps in time. We then add up all of the individual sessions to get the total time
    #   spent grading
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
    numStudents =  oneGradersActivity_df['Name'].nunique()
        
    cols_to_drop = ['start', 'end', 'max_end', 'new_group', 'group_id']
    oneGradersActivity_df = oneGradersActivity_df.drop(columns = cols_to_drop)
    
    ss.oneGradersActivity_df = oneGradersActivity_df
    ss.oneGradersSessions_df = oneGradersSessions_df
    
    return total_time, numStudents

def calculate_statistics():
    """ Loops through all of the graders, calculating statistics for each. """
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

def get_next_count(counts, curVal):
    if len(counts) > curVal:
        nextVal = counts[curVal][0]
    else:
        nextVal = None
    return nextVal
    
def get_top_three(row):
    """Function to get the top three graders for a single student."""
    # Use Counter to get the frequency of each string in the row (as a list)
    counts = Counter(row.values).most_common(5) # Do 5 because we may be white listing some graders
    
    output = []
    if ss.use_grader_white_list_input_local:
        whiteList = ast.literal_eval(ss['toml_dict']['user']['grader_white_list'])
    else:
        whiteList = []
   
    tries = 0
    while tries < 5:
        nextVal = get_next_count(counts, tries) # get_next_count(counts, tries)
        tries += 1
        if nextVal is not None and nextVal is not np.nan and nextVal not in whiteList:
            output.append(nextVal)
    
    output = output[:3]
    if len(output) < 3:
        output.extend(['–'] * (3 - len(output)))
            
    return pd.Series(output, index=['MC', 'nMC', 'nnMC'])

def highlight_outlier_graders(row):
    """Function to highlight the cells containing nMC and nnMC graders."""
    # Get the target values from 'nMC' and 'nnMC' columns for the current row
    target_values = [row['nMC'], row['nnMC']]
    
    # Define the default and highlight colors
    bg_color_match = 'background-color: yellow'
    bg_color_default = ''
    
    # Create a list of styles for each cell in the row
    # The condition checks if the cell's value is in target_values
    styles = [bg_color_match if cell_value is not None and cell_value in target_values else bg_color_default 
              for cell_value in row]
    
    return styles

def create_grader_df():
    """ Function to make a df containing 3 columns: Student, Time (graded), and Grader """

    allActivity_df = ss.allActivity_df
    
    time_cols = [col for col in allActivity_df.columns if col.startswith('G time')]
    last_cols = [col for col in allActivity_df.columns if col.startswith('G last')]

    grader_df = pd.concat([
                        pd.DataFrame({'Name': allActivity_df['Student\'s name'].values, 'Time': allActivity_df[t].values, 'Grader': allActivity_df[l].values}) 
                        for t, l in zip(time_cols, last_cols)
                        ], ignore_index=True)
                        
    grader_df = grader_df.dropna(subset=['Time'])
    
    grader_df = grader_df.sort_values(by=['Grader', 'Time'])
    grader_df = grader_df.reset_index(drop = True)

    # Get list of unique graders
    ss.graders = grader_df['Grader'].unique().tolist()

    ss.grader_df = grader_df
    calculate_statistics()
    
def handle_allActivity_upload():
    """Callback function to load allActivity df from csv, then calculate statistics """
    if st.session_state['allActivity_uploader_key'] is not None:
        allActivity_df = pd.read_csv(ss['allActivity_uploader_key'])
        allActivity_df['Student\'s name'] = allActivity_df['Student\'s name'].str.replace(r'\s*\(.*?\)', '', regex=True) # Strip e-mail addresses for brevity

        # Set all time columns to datetime objects
        cols = [col for col in allActivity_df.columns if col.startswith('G time')]
        allActivity_df[cols] = allActivity_df[cols].apply(pd.to_datetime)
        
        # Make a df that only contains columns starting with G last and use this to get all grader names
        temp_df = allActivity_df.copy()
        temp_df = temp_df.loc[:, temp_df.columns.str.startswith('G last')]
        all_graders = pd.unique(temp_df.values.ravel()).tolist()
        all_graders = [grader for grader in all_graders if type(grader) is str]
        
        # Look for papers with multiple graders. This is only useful for lab reports, which should have a single grader
        new_cols = temp_df.apply(get_top_three, axis=1)
        new_cols.columns = ['MC', 'nMC', 'nnMC']
        allActivity_df = pd.concat([allActivity_df, new_cols], axis=1)
        # allActivity_df[['MC', 'nMC', 'nnMC']] = temp_df.apply(get_top_three, axis=1) # Gives a performance warning?
        multipleGraders_df = allActivity_df[allActivity_df['nMC'] != '–'].copy()
        first_cols = ['order', 'Student\'s name', 'MC', 'nMC', 'nnMC']
        new_order_cols = first_cols + [col for col in multipleGraders_df.columns if col not in first_cols]
        multipleGraders_df = multipleGraders_df[new_order_cols]
        
        # Now highlight the outliers
        multipleGraders_df = multipleGraders_df.style.apply(highlight_outlier_graders, axis = 1)
        
        ss.multipleGraders_df = multipleGraders_df
        ss['allActivity_df'] = allActivity_df
        create_grader_df()

def reset_uploader():
    """Function to clear the uploaded files and show the uploader again."""
    ss['allActivity_df'] = None
    ss['grader_df'] = None

def update_use_grader_white_list_local():
    input = ss.use_grader_white_list_input_local

if 'toml_dict' not in ss:
    utils.read_prefs()
if 'allActivity_df' not in ss:
    ss['allActivity_df'] = None
if 'multipleGraders_df' not in ss:
    ss['multipleGraders_df'] = None
if 'grader_df' not in ss:
    ss['grader_df'] = None
if 'graderSummary_df' not in ss:
    ss.graderSummary_df = pd.DataFrame()
if 'oneGradersActivity_df' not in ss:
    ss.oneGradersActivity_df = pd.DataFrame()
if 'oneGradersSessions_df' not in ss:
    ss.oneGradersSessions_df = pd.DataFrame()

st.title('Analyze Grader Activity')

if 'use_grader_white_list_input_local' not in ss:
    ss.use_grader_white_list_input_local = ss['toml_dict']['user']['use_grader_white_list']

st.checkbox('Use grader white list? (This can be permanently changed in Settings.)',
            key = 'use_grader_white_list_input_local',
            on_change = update_use_grader_white_list_local)
            
text_str = 'Current white list (change in Settings): ' + ss['toml_dict']['user']['grader_white_list']
st.write(text_str)

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

if st.session_state['allActivity_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload All Activity csv here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'allActivity_uploader_key',
        on_change = handle_allActivity_upload
    )
else:
    st.write('#### :gray[All activity already uploaded.]')
    
    fig = px.histogram(ss.grader_df, x = 'Time')
    fig.update_traces(xbins_size = 'D1')
    fig.update_layout(bargap = 0.2)
    st.plotly_chart(fig, width = 'stretch')
    
    st.write('#### Papers with multiple graders')
    st.write('The less common grader(s) are highlighted in yellow. MC = most common grader, nMC = next most common grader, etc.')
    st.dataframe(ss.multipleGraders_df, hide_index=True)

    st.write('#### Summary of Each Grader\'s Activity')
    st.write('The grading time estimate is not meant to include regrades.')
    st.dataframe(ss.graderSummary_df)
    if len(ss.graderSummary_df) > 1:
        median_hrs = ss.graderSummary_df['Time grading (hr)'].median()
        median_min = ss.graderSummary_df['Time/student (min)'].median()
        st.write(f"Median grading time was {median_hrs} hrs or {median_min} min/student.")

    st.write('#### Display all Activity by Grader')
    st.selectbox(
        'Select a grader', # Label for the dropdown
        options = ss.graders, # The options to display
        index = None,
        key = 'selected_grader',                # Always start at none selected
        on_change = handle_grader_change
    )

    if ss.selected_grader is not None:
        fig2 = px.histogram(ss.oneGradersActivity_df, x = 'Time')
        fig2.update_traces(xbins_size = 'D1')
        fig2.update_layout(bargap = 0.2)
        st.plotly_chart(fig2, width = 'stretch')
    
        st.write('#### All Grading Sessions by Grader') 
        st.write('Break is the time between the last grading session and the current session.')   
        st.dataframe(ss.oneGradersSessions_df)

        st.write('#### All Activity by Grader')
        st.dataframe(ss.oneGradersActivity_df)

utils.shared_sidebar()
