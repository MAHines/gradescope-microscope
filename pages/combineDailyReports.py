import streamlit as st
import pandas as pd
import plotly.express as px
import utils
import ast
from datetime import datetime, timedelta
from streamlit import session_state as ss
from pathlib import Path

def handle_allDailyActivity_upload():
    """Callback function to load all daily grading from (potentially multiple) csv's """
    uploaded_files = ss.allDailyActivity_uploader_key
    if uploaded_files:
        allDailyGrading_df = None
        allDailyRegrading_df = None
        for file in uploaded_files:
            all_sheets = pd.read_excel(file, sheet_name = None)
            
            regrades_df = None
            for sheet_name, df in all_sheets.items():
                if sheet_name == 'Daily_Grading':
                    dailyGrading_df = df
                    allDailyGrading_df = pd.concat([df for df in [allDailyGrading_df, dailyGrading_df] if df is not None], ignore_index=True)
                elif sheet_name == 'Daily_Regrading':
                    dailyRegrading_df = df
                    allDailyRegrading_df = pd.concat([df for df in [allDailyRegrading_df, dailyRegrading_df] if df is not None], ignore_index=True)
    
    allDaily_df = pd.concat([df for df in [allDailyGrading_df, allDailyRegrading_df] if df is not None], ignore_index=True)
    ss.allDaily_df = allDaily_df
#     st.dataframe(allDailyGrading_df)
#     st.dataframe(allDailyRegrading_df) 

def handle_assignedActivity_upload():
    """Callback function to load assigned activity from csv """
    if ss['assignedActivity_uploader_key'] is not None:
        assignedActivity_df = pd.read_csv(ss.assignedActivity_uploader_key)
        assignedActivity_df['Day'] = pd.to_datetime(assignedActivity_df['Day'])
        
        # Remove all entries for white-listed people
        white_list = ast.literal_eval(ss['toml_dict']['user']['grader_white_list'])
        ss.allDaily_df = ss.allDaily_df[~ss.allDaily_df['Name'].isin(white_list)]
        
        # Get a list of all TAs
        allTAs_df = pd.DataFrame(ss.allDaily_df['Name'].unique(), columns = ['Name'])
        ss.allTAs_df = allTAs_df
        
        # Make a new df containing all of the assigned activity
        allAssignedActivity_df = assignedActivity_df.merge(allTAs_df, how = 'cross')
        allAssignedActivity_df = allAssignedActivity_df.drop(columns = 'Activity')
        
        # Concatenate with the grading data
        ss.allDaily_df = pd.concat([ss.allDaily_df, allAssignedActivity_df])
        
        # Find the weekly data
        weekly_df = ss.allDaily_df.groupby(['Name', pd.Grouper(key='Day', freq='W-MON')])['duration_min'].sum().reset_index(name='total_weekly_min')
        weekly_df['total_weekly_hr'] = weekly_df['total_weekly_min']/60.0
        ss.weekly_df = weekly_df

        weeklyAssigned_df = allAssignedActivity_df.groupby(['Name', pd.Grouper(key='Day', freq='W-MON')])['duration_min'].sum().reset_index(name='total_weekly_min')
        weeklyAssigned_df['total_weekly_hr'] = weeklyAssigned_df['total_weekly_min']/60.0
        ss.weeklyAssigned_df = weeklyAssigned_df
        
def reset_daily_uploader():
    """Function to clear the uploaded files and show the uploader again."""
    ss.allDaily_df = None
    ss.weekly_df = None
            
def prepare_time_plot(grader):
    
    grader_time_df = ss.weekly_df[ss.weekly_df['Name'] == grader]
    grader_time_df = grader_time_df.drop(columns = ['total_weekly_min'])
    grader_assignedTime_df = ss.weeklyAssigned_df[ss.weeklyAssigned_df['Name'] == grader]
    grader_assignedTime_df = grader_assignedTime_df.drop(columns = ['total_weekly_min'])
    grader_assignedTime_df = grader_assignedTime_df.rename(columns = {'total_weekly_hr': 'assign_weekly_hr'})
    merged_df = pd.merge(grader_time_df, grader_assignedTime_df, on = ['Name', 'Day'])
    merged_df['grading_weekly_hr'] = merged_df['total_weekly_hr'] - merged_df['assign_weekly_hr']
    
    myTitle = f'Weekly Hours for {grader}'
    fig = px.bar(merged_df,
                    x = 'Day',
                    y = ['assign_weekly_hr', 'grading_weekly_hr'],
                    title = myTitle,
                    labels = {'assign_weekly_hr': 'Assigned', 'grading_weekly_hr': 'Grading'})
    new_names = {'assign_weekly_hr': 'Assigned Hrs', 'grading_weekly_hr': 'Grading'}
    fig.for_each_trace(lambda t: t.update(name = new_names[t.name]))    
    
    fig.add_hline(y = 20,
                    line_dash = 'dash',
                    line_color = 'red',
                    annotation_text = 'max',
                    annotation_position = 'top right')
    
    fig.update_layout(yaxis_title = 'Hours',
                      xaxis_title = 'Week',
                      legend_title_text = 'Activity')
    
    return fig

if 'toml_dict' not in ss:
    utils.read_prefs()
if 'allDaily_df' not in ss:
    ss.allDaily_df = None
if 'weekly_df' not in ss:
    ss.weekly_df = None

st.set_page_config(layout='wide')

st.title('Combine Daily Grading Reports')

if ss.allDaily_df is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload DailySum_GS_*.xlsx here:",
        type=['xlsx'],
        accept_multiple_files=True,
        key = 'allDailyActivity_uploader_key',
        on_change = handle_allDailyActivity_upload
    )
else:
    st.write('#### :gray[All activity already uploaded.]')
   
    st.button("Reset or work on a different course.", 
            on_click=reset_daily_uploader,
            type = 'primary')

    st.file_uploader(
        "Upload Assigned Activity.csv here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'assignedActivity_uploader_key',
        on_change = handle_assignedActivity_upload
    )
    
    if ss.weekly_df is not None:
        st.write('#### All TA Activity')
        
        for row in ss.allTAs_df.itertuples():
            fig = prepare_time_plot(row.Name)
            st.plotly_chart(fig, width = 'content')
            
        empty_df = pd.DataFrame()   # Makes pdf output better
        st.dataframe(empty_df)        

                        
utils.shared_sidebar()
