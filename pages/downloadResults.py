import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime, date
import re
import keyring as kr
import os
from streamlit import session_state as ss
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import time
import utils

TIMEOUT = 30

def GS_login_password():
    """ Allows a user to log in with an e-mail address and password stored in the user's login
            keychain. """
    
    # Initialize WebDriver
    # This process can be run headless by uncommenting the commands below; however, the
    #   speedup was (suprisingly) quite modest. Better to run headed
#     chrome_options = Options()
#     chrome_options.add_argument("--headless=new")
#     chrome_options.add_argument("--window-size=1920,1080")
#     chrome_options.add_argument("--disable-gpu") 
#     chrome_options.add_argument("--no-sandbox") 
#     driver = webdriver.Chrome(options=chrome_options) # Initialize WebDriver
    driver = webdriver.Chrome()
    driver.get("https://www.gradescope.com/login")
    
    # Use WebDriverWait to handle dynamic elements
    wait = WebDriverWait(driver, TIMEOUT)
    
    # Locate fields and send keys
    email_field = wait.until(EC.presence_of_element_located((By.NAME, "session[email]")))
    password_field = driver.find_element(By.NAME, "session[password]")
    login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
    
    # Retrieve login from system keyring
    sysUsername = os.getlogin()     # the username on your computer, not Gradescopee.g., mah
    username = kr.get_password("gradescope_extUsername", sysUsername)
    password = kr.get_password("gradescope_extPassword", sysUsername)
    
    # Send credential to Gradescope
    email_field.send_keys(username)
    password_field.send_keys(password)
    login_button.click()
    
    div_class_name = 'courseList--term'
    wait = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
            )
    
    ss['driver'] = driver # Store the driver for later access.

def GS_login_user():
    """ Allow the user to log in to Gradescope using any mechanism. The method times out after
            3 minutes. """
       
    # Initialize webdriver
    driver = webdriver.Chrome()
    try:
        driver.get("https://www.gradescope.com/login")
            
        # Wait up to 3 minutes for the user to log in
        div_class_name = 'courseList--term'
        wait = WebDriverWait(driver, 180).until(
                EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
                )
        
        ss['driver'] = driver # Store the driver for later access.
    except TimeoutException as e:
        st.write((f"Page load timed out: {e.message}"))
    except WebDriverException as e:
        st.write(f"WebDriver exception occurred: {e.message}") # Handle browser crash or network issues

def GS_login():
    """ Logs in to Gradescope either using a stored password or "manually." """
    if ss['toml_dict']['user']['password_login']:
        GS_login_password()
    else:
        GS_login_user() 
           
def get_questions():
    """ Returns a list of (question_id, question_num) pairs obtained from the page accessed by the statistics
        button in the web interface """
        
    driver = ss['driver']
    url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/assignments/'
            + str(ss['assignment_id']) + '/statistics')
    driver.get(url)
    div_class_name = 'statisticsTable'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    
    
    soup = BeautifulSoup(driver.page_source, 'lxml')
    questions = []

    divs = soup.find_all('div', class_='statisticsItem--title')
    if divs:
        for div in divs:
            a_tag = div.find('a')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag.get('href')
                question_id = href.split('/questions/')[1].split('/')[0]
                text = div.get_text(strip = True)
                question_num = text.split(':')[0]
                questions.append([question_id, question_num])

    ss['questions'] = questions

def get_rubric_items(question_index):
    """ Returns a list of (question_id, question_num, rubric_items) for question question_index where 
        rubric_items is a list of the form (rubric_item_id, rubric_item_name).
        These data are extracted from the statistic page that appears after a specific
        question is clicked """
    driver = ss['driver']
    question_id = ss['questions'][question_index][0]
    question_num = ss['questions'][question_index][1]
    url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/questions/'
            + str(question_id) + '/statistics')
    driver.get(url)
    div_class_name = 'statisticsSummary'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
        )
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    
    
    soup = BeautifulSoup(driver.page_source, 'lxml')
    tds = soup.find_all('td', class_='statisticsTable--column questionRubricTable--column-title')
    
    rubric_items = []
    if tds:
        for td in tds:
            a_tag = td.find('a')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag['href']
                rubric_item_id = href.split('/rubric_items/')[1].split('/')[0]
                
                # Need a unique ID that is not too long
                rubric_item_name = a_tag.get_text(strip = True)[:15] # Return only first 15 chars
                
                rubric_items.append([rubric_item_id, rubric_item_name])
    
    return ([question_id, question_num, rubric_items])
    
def get_all_rubric_items():
    """ Iterates through all of the questions, collecting the rubric items for each one """
    ss['all_items'] = []
    for index, question in enumerate(ss['questions']):
        rubric_items = get_rubric_items(index)
        ss['all_items'].append(rubric_items)

def get_assignment_data():
    """ Once all of the questions and rubric items are extracted from each question in the
        assignment, this function collects all of the grading data for each rubric item.
        The output is a dataframe that contains a grading record for each student who
        submitted an assignment """

    driver = ss['driver']
    activity_df = ss['activity_df']
    current_year = datetime.now().year  # May be wrong if we are analyzing historical data
    for item in ss['all_items']:
        question_id, question_num, rubric_items = item
        for rubric_item in rubric_items:
            rubric_item_id, rubric_item_name = rubric_item
            url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/questions/' + str(question_id)
                    + '/rubric_items/' + str(rubric_item_id))
            driver.get(url)
            
            div_class_name = '.table--header.table--header-withFilter'
            try:
                # Wait until the element with the specified class is visible
                visible_div = WebDriverWait(driver, TIMEOUT).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, div_class_name))
                )
            except TimeoutException:
                st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.") 
            except Exception as e:
                st.write(f"An unexpected exception occurred: {e}")  
                
            numApplied = int(visible_div.text.split()[0])
            
            # We load each individual table into rubric_item_df, reformat, then merge with activity_df
            if numApplied > 0:
                try:
                    table_element = WebDriverWait(driver, TIMEOUT).until(
                        EC.presence_of_element_located((By.XPATH, "//table[@id='DataTables_Table_0']")) # Replace with your table's XPath or CSS selector
                    )
                except TimeoutException:
                    st.write("Timed out waiting for the table DataTables_Table_0 to become visible.") 
                    
                table_html = table_element.get_attribute('outerHTML')  
                rubric_item_df = pd.read_html(StringIO(table_html))[0]
                rubric_item_df.drop(columns=['Sections'], inplace=True)
                
                # Convert the Graded time column to a proper datetime
                time_part = rubric_item_df['Graded time'].str.extract(r'^(.*?)\s*\(')[0].str.strip()
                full_datetime_str = str(current_year) + ' ' + time_part.str.replace(" at ", " ")
                # rubric_item_df['Graded time'] = full_datetime_str
                rubric_item_df['Graded time'] = pd.to_datetime(full_datetime_str, format='%Y %b %d %I:%M%p')
                
                # Rename the columns
                new_graded_time = 'G time ' + str(question_num) + ' ' + str(rubric_item_name)
                new_last_graded = 'G last ' + str(question_num) + ' ' + str(rubric_item_name)
                
                # Need to test for duplicate column names because of shortening
                while True:
                    if new_graded_time not in activity_df.columns:
                        break
                    new_graded_time += '…'
                    new_last_graded += '…'
                
                rename_mapping = {'Graded time': new_graded_time,
                                  'Last graded by': new_last_graded}
                rubric_item_df = rubric_item_df.rename(columns = rename_mapping)
                
                # Set the index
                # rubric_item_df = rubric_item_df.set_index('Student\'s name')
                
                activity_df = pd.merge(activity_df, rubric_item_df, on = 'Student\'s name', how = 'left')
    
    ss['activity_df'] = activity_df
    
def get_students_in_order():
    """ We need to be able to match a student name with the number the TAs were assigned. To 
        do this, we pull up the first question and get the student list. """
    
    driver = ss['driver']
    url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/questions/'
            + str(ss['questions'][0][0] + '/submissions'))
    driver.get(url)
    try:
        # Wait until the element with the specified class is visible
         table_element = WebDriverWait(driver, TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, "//table[@id='question_submissions']")) # Replace with your table's XPath or CSS selector
                )
    except TimeoutException:
        st.write("Timed out waiting for the table question_submissions to become visible.")    

    table_html = table_element.get_attribute('outerHTML')  
    students_df = pd.read_html(StringIO(table_html))[0]
    ss['activity_df'] = students_df[['User']]
    ss['activity_df'].index += 1
    ss['activity_df'] = ss['activity_df'].rename(columns = {'User': 'Student\'s name'})
    ss['activity_df'] = ss['activity_df'].rename_axis(index="order")
    ss['activity_df'] = ss['activity_df'].reset_index()
    
def process_the_assignment():
    """ After the user has selected a course and assignment, this function does all of the processing. """
    ss.downloaded_assignment = ss.selected_assignment   # Prevents problems upon page switching
    if 'driver' not in ss:
        GS_login()
    get_questions()
    get_students_in_order()
    get_all_rubric_items()
    get_assignment_data()
        
def previousTerm(currentTerm):
    semester, year_str = currentTerm.split()
    year = int(year_str)
    if semester == 'Fall':
        return f'Summer {year}'
    elif semester == 'Summer':
        return f'Spring {year}'
    elif semester == 'Spring':
        return f'Fall {year - 1}'
    else:
        return 'Invalid Semester'

def currentTerm():
    """ Guesses the current semester based on today's date. """
    today = date.today()
    springEnd = datetime.strptime('May 30 2025', '%b %d %Y').date().replace(year=today.year)
    summerEnd = datetime.strptime('Aug 15 2025', '%b %d %Y').date().replace(year=today.year)
    term = 'Spring' if today < springEnd else ('Summer' if today < summerEnd else 'Fall')
    curTerm = term + ' ' + str(today.year)
    return curTerm

def get_courses(recent = True):
    """ Gets a dictionary of the user's courses. If recent = True, limit the list to courses 
        in the last year. """
    driver = ss.driver
    url = 'https://www.gradescope.com/'
    driver.get(url)
    
    div_class_name = 'courseList'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    

    soup = BeautifulSoup(driver.page_source, 'lxml')
    curTerm = currentTerm()
    prevTerm = previousTerm(curTerm)
    recentTerms = [curTerm, prevTerm, previousTerm(prevTerm)]
    
    course_list_soup = soup.find('div', class_='courseList')
    terms = course_list_soup.find_all('div', class_='courseList--term')
    
    course_ids = []
    course_names = []
    for term in terms:
        term_name = term.text.strip()
        
        # Find the next course box
        term_course_list = term.find_next('div', class_='courseList--coursesForTerm')
        a_tags = term_course_list.find_all('a', class_ = 'courseBox')
        for a_tag in a_tags:
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag.get('href')
                course_id = href.split('/')[-1] 
                course_name_tag = a_tag.find('h3', class_ = 'courseBox--shortname')
                course_name = course_name_tag.text.strip() if course_name_tag else 'No name'
                course_full_name = term_name + ' ' + course_name
                if recent:
                    if term_name in recentTerms:
                        course_ids.append(course_id)
                        course_names.append(course_full_name)
                else:
                    course_ids.append(course_id)
                    course_names.append(course_full_name)
    course_dict = {k: v for k, v in zip(course_names, course_ids)}
    ss['course_dict'] = course_dict
    
def get_assignments(course_id):
    """ Gets a dictionary of all of the assignments associated with the course_id. Returns
        a dictionary of courses. """
    driver = ss.driver
    url = 'https://www.gradescope.com/courses/' + str(course_id) + '/assignments'
    driver.get(url)
    
    div_class_name = 'l-table'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    

    soup = BeautifulSoup(driver.page_source, 'lxml')

    assignment_ids = []
    assignment_names = []

    divs = soup.find_all('div', class_ = 'table--primaryLink assignments--rowTitleContainer')
    for div in divs:
        a_tag = div.find('a')
        if a_tag and 'href' in a_tag.attrs:
            href = a_tag.get('href')
            assignment_ids.append(href.split('/')[-1])
            assignment_names.append(a_tag.text)
    
    assignment_dict = {k:v for k, v in zip(assignment_names, assignment_ids)}
    ss.assignment_dict = assignment_dict

def handle_course_change():
    """ Handles course selection change drop down. When the course changes, get a list
        of all assignments for that course and reset the assignment selector to none """
    ss.course_id = ss.course_dict[ss.selected_course]
    get_assignments(ss.course_id)
    ss.selected_assignment = None
    ss.assignment_id = None
    
def handle_assignment_change():
    """ Handles assignment selection change drop down """
    selected_assignment = ss.selected_assignment
    ss['assignment_id'] = ss.assignment_dict[selected_assignment]

def handle_evaluations_download():
    driver = ss.driver
    url = ('https://gradescope.com/courses/' + str(ss.course_id) + '/assignments/'
            + str(ss.assignment_id) + '/export_evaluations')
    driver.get(url)
    
def handle_gradescope_logout():
    driver = ss.driver
    driver.quit()
    ss.driver = None    
                    
if 'driver' not in ss:
    ss['driver'] = None
if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'course_dict' not in ss:
    ss.course_dict = None
if 'assignment_dict' not in ss:
    ss.assignment_dict = None
if 'assignment_id' not in ss:
    ss.assignment_id = None
if 'course_id' not in ss:
    ss.course_id = None
if 'selected_course' not in ss:
    ss.selected_course = None
if 'selected_assignment' not in ss:
    ss.selected_assignment = None
if 'downloaded_assignment' not in ss:
    ss.downloaded_assignment = None

st.title('Download Assignment Grading Data')

text_str = "Use the button below to log in to Gradescope. If you are NOT using automated password login,  "
text_str += "you will have 3 min to complete the login in the browser window after you push the button. "
text_str += "In either case, leave the browser window open after you finish."
st.write(text_str)

if ss.driver is None:
    if st.button("Log in to Gradescope", type = 'primary'):
        GS_login()
        get_courses()

if ss['course_dict'] is not None:
    st.selectbox(
        'Select a course', # Label for the dropdown
        options = list(ss['course_dict'].keys()), # The options to display
        key = 'selected_course',
        index = None,                # Always start at none selected
        on_change = handle_course_change
    )
    
if ss['assignment_dict'] is not None:
    st.selectbox(
        'Select an assignment', # Label for the dropdown
        options = list(ss['assignment_dict'].keys()), # The options to display
        key = 'selected_assignment',
        index = None,                # Always start at none selected
        on_change = handle_assignment_change
    )
    
if ss.course_id is not None and ss.assignment_id is not None:
    text_str = 'After pushing the button, the script will loop through the assignment in Gradescope, '
    text_str += 'finding all of the rubric items. It will then loop through each rubric item and '
    text_str += 'record the grading activity associated with that item. At the end, you will be '
    text_str += 'given the opportunity to save the grading data in a csv for analysis.'
    st.write(text_str)
    if st.button("Start Downloading", type = 'primary'):
        status_placeholder = st.empty()
        start_time = time.perf_counter()
        status_placeholder.write("Downloading in progress...")
        process_the_assignment()
        end_time = time.perf_counter()
        elapsed_time = (end_time - start_time)/60
        status_placeholder.write(f"Elapsed time: {elapsed_time:.1f} min")

if 'activity_df' in ss:
    st.dataframe(ss['activity_df'])
    
    twoWords = ss.downloaded_assignment.split()[:2] # Use first two words of assignment
    shortAssignmentName  = "_".join(twoWords) 
    file_name = shortAssignmentName + '_GS_activity' + '_' + datetime.now().strftime("%b_%d") + '.csv'
    combined_data = ss['activity_df'].to_csv(index = False, header = True).encode('utf-8')
    st.download_button(label = 'Download Gradescope Activity Report as csv',
                    data = combined_data,
                    file_name = file_name,
                    mime = 'text/csv',
                    type = 'primary')
                    
    text_str = 'You can use the button below to \'Export Evaluations\' for this assignment. '
    text_str += 'Your Chromium window may say \'insecure download blocked.\' If so, select '
    text_str += '\'Keep\' and then click the download icon ↗️.'
    st.write(text_str)
    
    st.button('Download Evaluations folder',
                type = 'primary',
                on_click = handle_evaluations_download)
        
if ss.driver is not None:
    st.button('Log out of Gradescope',
                type = 'primary',
                on_click = handle_gradescope_logout)
                
utils.shared_sidebar()
