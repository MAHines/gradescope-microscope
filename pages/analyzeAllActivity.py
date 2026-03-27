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

def analyze_one(acts_df, grader):
    """ Analyzes the activity of a single grader. Called repeatedly to analyze all graders. """

    # We need to distinguish between actual breaks and time spent, for example, reading reports
    #   To do this, we use the common approach of saying breaks longer than the 95th percentile
    #   are actual breaks. This avoids problems with different types of assignments having
    #   different grading patterns, and different graders having different behaviors. Nevertheless,
    #   there needs to be an upper limit on this, because some people are taking a break after each 
    #   report (fair enough). Also, our times are only saved with 1 min resolution
    temp_df = acts_df[acts_df['Grader'] == grader].copy()
    temp_df['pause_time'] = temp_df['Time'].diff()
    percentile_96 = min(temp_df['pause_time'].quantile(0.96), timedelta(minutes = 6.0))
    if percentile_96 < timedelta(minutes = 1.0):
        percentile_96 = timedelta(minutes = 1.0)
    
    oneActivity_df = acts_df[acts_df['Grader'] == grader].copy()
    oneActivity_df['start'] = oneActivity_df['Time'] - percentile_96
    oneActivity_df['end'] = oneActivity_df['Time']
    
    # This is the key bit. We convert a log of individual actions into distinct "sessions" based
    #   an gaps in time. We then add up all of the individual sessions to get the total time
    #   spent grading
    oneActivity_df['max_end'] = oneActivity_df['end'].cummax().shift().fillna(oneActivity_df['start'].min())
    oneActivity_df['start'] = pd.to_datetime(oneActivity_df['start'], errors = 'coerce')
    oneActivity_df['new_group'] = oneActivity_df['start'] > oneActivity_df['max_end']
    oneActivity_df['group_id'] = oneActivity_df['new_group'].cumsum()
    
    oneSessions_df = oneActivity_df.groupby('group_id').agg(
        merged_start=('start', 'min'),
        merged_end=('end', 'max')
    )
    
    # Calculate duration and sum
    oneSessions_df['duration'] = oneSessions_df['merged_end'] - oneSessions_df['merged_start']
    oneSessions_df['break'] = oneSessions_df['merged_end'].diff() - oneSessions_df['duration']
        
    cols_to_drop = ['start', 'end', 'max_end', 'new_group', 'group_id']
    oneActivity_df = oneActivity_df.drop(columns = cols_to_drop)
    
    return oneActivity_df, oneSessions_df

def analyze_one_grader(grader):
    """ Analyzes the activity of a single grader. Called repeatedly to analyze all graders. """

    oneGradersActivity_df, oneGradersSessions_df = analyze_one(ss.grading_acts_df, grader)   
    graders_total_time = oneGradersSessions_df['duration'].sum().total_seconds()/3600
    graders_numStudents =  oneGradersActivity_df['Name'].nunique()
    
    ss.oneGradersActivity_df = oneGradersActivity_df
    ss.oneGradersSessions_df = oneGradersSessions_df
        
    oneRegradersActivity_df, oneRegradersSessions_df = analyze_one(ss.regrading_acts_df, grader)   
    regraders_total_time = oneRegradersSessions_df['duration'].sum().total_seconds()/3600
    regraders_numStudents =  oneRegradersActivity_df['Name'].nunique()
    
    ss.oneRegradersActivity_df = oneRegradersActivity_df
    ss.oneRegradersSessions_df = oneRegradersSessions_df
    
    return graders_total_time, graders_numStudents, regraders_total_time, regraders_numStudents

def calculate_statistics():
    """ Loops through all of the graders, calculating statistics for each. """
    graderSummary_df = pd.DataFrame(ss.graders, columns=['Grader'])
    
    graderSummary_df['numGraded'] = np.nan
    graderSummary_df['Grading time (hr)'] = np.nan
    graderSummary_df['Grading time/student (min)'] = np.nan    
    graderSummary_df['numRegraded'] = np.nan
    graderSummary_df['Regrading time (hr)'] = np.nan
    graderSummary_df['Regrading time/student (min)'] = np.nan    

    for grader in ss.graders:
        graders_total_time, graders_numStudents, regraders_total_time, regraders_numStudents = analyze_one_grader(grader)
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'numGraded'] = graders_numStudents
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Grading time (hr)'] = round(graders_total_time, 2)
        if graders_numStudents > 0:
            graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Grading time/student (min)'] = round(60 * graders_total_time/graders_numStudents, 1)
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'numRegraded'] = regraders_numStudents
        graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Regrading time (hr)'] = round(regraders_total_time, 2)
        if regraders_numStudents > 0:
            graderSummary_df.loc[graderSummary_df['Grader'] == grader, 'Regrading time/student (min)'] = round(60 * regraders_total_time/regraders_numStudents, 1)

    ss.graderSummary_df = graderSummary_df

def reset_uploader():
    """Function to clear the uploaded files and show the uploader again."""
    ss['grading_acts_df'] = None
    ss.regrades_df = None

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

def create_grading_acts_df():
    """ Function to make a df containing 3 columns: Student, Time (graded), and Grader """

    allActivity_df = ss.allActivity_df
    
    time_cols = [col for col in allActivity_df.columns if col.startswith('G time')]
    last_cols = [col for col in allActivity_df.columns if col.startswith('G last')]

    allGrading_acts_df = pd.concat([
                        pd.DataFrame({'Name': allActivity_df['Student\'s name'].values, 'Time': allActivity_df[t].values, 'Grader': allActivity_df[l].values}) 
                        for t, l in zip(time_cols, last_cols)
                        ], ignore_index=True)
                        
    allGrading_acts_df = allGrading_acts_df.dropna(subset=['Time'])
    
    allGrading_acts_df = allGrading_acts_df.sort_values(by=['Grader', 'Time'])
    allGrading_acts_df = allGrading_acts_df.reset_index(drop = True)
    
    grading_acts_df = allGrading_acts_df[allGrading_acts_df['Time'] < ss.regrading_start].copy()
    regrading_acts_df = allGrading_acts_df[allGrading_acts_df['Time'] >= ss.regrading_start].copy()    

    # Get list of unique graders
    ss.graders = allGrading_acts_df['Grader'].unique().tolist()

    ss.allGrading_acts_df = allGrading_acts_df
    ss.grading_acts_df = grading_acts_df
    ss.regrading_acts_df = regrading_acts_df
    calculate_statistics()
    
def handle_allActivity_upload():
    """Callback function to load allActivity df from csv, then calculate statistics """
    if ss['allActivity_uploader_key'] is not None:
        all_sheets = pd.read_excel(ss.allActivity_uploader_key, sheet_name = None)
        
        regrades_df = None
        for sheet_name, df in all_sheets.items():
            if sheet_name == 'Grading':
                allActivity_df = df
            elif sheet_name == 'Regrading':
                regrades_df = df
        
        allActivity_df['Student\'s name'] = allActivity_df['Student\'s name'].str.replace(r'\s*\(.*?\)', '', regex=True) # Strip e-mail addresses for brevity

        # Set all time columns to datetime objects
        cols = [col for col in allActivity_df.columns if col.startswith('G time')]
        allActivity_df[cols] = allActivity_df[cols].apply(pd.to_datetime)
        if regrades_df is not None:
            regrades_df['Submission_time'] = regrades_df['Submission_time'].apply(pd.to_datetime)
        
        # Make a df that only contains columns starting with G last and use this to get all grader names
        temp_df = allActivity_df.copy()
        temp_df = temp_df.loc[:, temp_df.columns.str.startswith('G last')]
        all_graders = pd.unique(temp_df.values.ravel()).tolist()
        all_graders = [grader for grader in all_graders if type(grader) is str]
        
        # Use the time of the first regrade to mark the beginning of regrading
        if regrades_df is not None:
            ss.regrading_start = regrades_df['Submission_time'].min()
        else:
            ss.regrading_start = pd.Timestamp.now()
        
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
        ss.allActivity_df = allActivity_df
        ss.regrades_df = regrades_df
        create_grading_acts_df()

def reset_uploader():
    """Function to clear the uploaded files and show the uploader again."""
    ss['allActivity_df'] = None
    ss['grading_acts_df'] = None
    ss.regrades_df = None
    ss.df_combinedForFig = None

def update_use_grader_white_list_local():
    input = ss.use_grader_white_list_input_local

if 'toml_dict' not in ss:
    utils.read_prefs()
if 'allActivity_df' not in ss:
    ss['allActivity_df'] = None
if 'multipleGraders_df' not in ss:
    ss['multipleGraders_df'] = None
if 'grading_acts_df' not in ss:
    ss['grading_acts_df'] = None
if 'regrading_acts_df' not in ss:
    ss['regrading_acts_df'] = None
if 'regrades_df' not in ss:
    ss.regrades_df = None
if 'graderSummary_df' not in ss:
    ss.graderSummary_df = pd.DataFrame()
if 'oneGradersActivity_df' not in ss:
    ss.oneGradersActivity_df = pd.DataFrame()
if 'oneGradersSessions_df' not in ss:
    ss.oneGradersSessions_df = pd.DataFrame()
if 'regrading_start' not in ss:
    ss.regrading_start = pd.Timestamp.now()
if 'df_combinedForFig' not in ss:
    ss.df_combinedForFig = None

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

def prepFig1():
    temp1 = ss.grading_acts_df.copy()
    temp1['series'] = 'Grading'
    temp2 = ss.regrading_acts_df.copy()
    temp2['series'] = 'Regrading'
    df_combinedForFig = pd.concat([temp1, temp2])
    ss.df_combinedForFig = df_combinedForFig
    
if st.session_state['allActivity_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload GS_activity…xlsx here:",
        type=['xlsx'],
        accept_multiple_files=False,
        key = 'allActivity_uploader_key',
        on_change = handle_allActivity_upload
    )
else:
    st.write('#### :gray[All activity already uploaded.]')
    
    st.write(f'Regrading started {ss.regrading_start.strftime("%b %d, %Y at %I:%M %p")}')
    
    if ss.df_combinedForFig is None:
        prepFig1()    
    
    text_str = 'Drag horizontally from left to right (or right to left) to zoom in the plotting range. '
    text_str += 'Double click anywhere in the graph to reset. Be aware that '
    text_str += 'large classes with complicated rubrics and small bin sizes can lead to sluggish interactive graphs.'
    st.write(text_str)
    bin_type = st.selectbox("Select Bin Size", ['1 day', '1 hr', '30 min', '10 min'])
    if bin_type == '10 min':
        xbins_size = 10 * 60 * 1000
    elif bin_type == '30 min':
        xbins_size = 30 * 60 * 1000
    elif bin_type == '1 hr':
        xbins_size = 60 * 60 * 1000
    else: # '1 day'
        xbins_size = 24 * 60 * 60 * 1000

    fig = px.histogram(ss.df_combinedForFig,
                       x = 'Time',
                       color = 'series',
                       barmode = 'overlay',
                       color_discrete_sequence = ['blue', 'red'])
    fig.update_traces(xbins_size=xbins_size)

    fig.update_layout(bargap = 0.1)
    st.plotly_chart(fig, width = 'stretch')
    
    st.write('#### Papers with multiple graders (Useful for lab reports, not exams)')
    st.write('The less common grader(s) are highlighted in yellow. MC = most common grader, nMC = next most common grader, etc.')
    total_cells = ss.multipleGraders_df.data.size
    if total_cells > 262144:
        pd.set_option("styler.render.max_elements", total_cells)
    st.dataframe(ss.multipleGraders_df, 
                 column_config={"link": st.column_config.LinkColumn("link", display_text="link")},
                 hide_index=True)

    st.write('#### Summary of Each Grader\'s Activity')
    st.dataframe(ss.graderSummary_df, hide_index = True)
    if len(ss.graderSummary_df) > 1:
        median_hrs = ss.graderSummary_df['Grading time (hr)'].median()
        median_min = ss.graderSummary_df['Grading time/student (min)'].median()
        total_hrs = ss.graderSummary_df['Grading time (hr)'].sum()
        total_students = len(ss.allActivity_df)
        text_str = (f'Median grading time was {median_hrs} hrs or {median_min} min/student. '
                    f'Total grading time was {total_hrs} hrs or {60*total_hrs/total_students:.2f} min/student.')
        st.write(text_str)

    st.write('#### Display all Activity by Grader')
    st.selectbox(
        'Select a grader', # Label for the dropdown
        options = ss.graders, # The options to display
        index = None,
        key = 'selected_grader',                # Always start at none selected
        on_change = handle_grader_change
    )

    if ss.selected_grader is not None:
        temp3 = ss.oneGradersActivity_df.copy()
        temp3['series'] = 'Grading'
        temp4 = ss.oneRegradersActivity_df.copy()
        temp4['series'] = 'Regrading'
        df_combinedForFig2 = pd.concat([temp3, temp4])
        fig2 = px.histogram(df_combinedForFig2,
                           x = 'Time',
                           color = 'series',
                           barmode = 'overlay',
                           color_discrete_sequence = ['blue', 'red'])
        fig2.update_layout(bargap = 0.2)
        st.plotly_chart(fig2, width = 'stretch')
    
        st.write('#### All Grading by Grader')
        st.dataframe(ss.oneGradersActivity_df, hide_index = True)
    
        st.write('#### All Regrading by Grader')
        st.dataframe(ss.oneRegradersActivity_df, hide_index = True)
    
    if ss.regrades_df is not None:
        st.write('### All regrading activity')
        text_str = 'If the text in a cell is too long to read, double-click for a better view. '
        st.write(text_str)
        if 'regrades_df' in ss:
            st.dataframe(ss['regrades_df'],
                            hide_index=True, 
                            column_config={"link": st.column_config.LinkColumn("link", display_text="link")},
                            row_height=150)

        

utils.shared_sidebar()
