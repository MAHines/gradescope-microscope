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
import json

TIMEOUT = 30    # I got occasional timeouts at 10 sec, so upped to 30 sec

# ss.questions: A list of (question_id, question_num)
# ss.assignment_dict: A dict of assignment_names: assignment_ids
# ss.all_items: a list of (question_id, question_num, rubric_items) for question question_index where 
#         rubric_items is a list of the form (rubric_item_id, rubric_item_name)
# ss.activity_df: The main datafrome
# ss.regrades_df: The dataframe of regrading data
        
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
            + str(ss['assignment_id']) + '/statistics') #?sectionIds%5B%5D=1061335
    if ss.section_with_min_studentsID is not None:
        url = url + '?sectionIds%5B%5D=' + str(ss.section_with_min_studentsID)
    driver.get(url)

    div_ID = 'page-switcher-tabpanel-QUESTIONS_PAGE'    # This div is also on unsubmitted assignments
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.ID, div_ID))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    
    
    soup = BeautifulSoup(driver.page_source, 'lxml')
    
    div = soup.find('div', class_='blankState--heading')
    if div:
        st.error('This assignment appears to be ungraded. Choose a different assignment.')
        st.stop()
        
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
            + str(question_id) + '/statistics')  #?sectionIds%5B%5D=1061335
    if ss.section_with_min_studentsID is not None:
        url = url + '?sectionIds%5B%5D=' + str(ss.section_with_min_studentsID)

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
    
def get_regrades_df():
    """ Returns a list of regrade requests for a particular assignment """
    driver = ss['driver']
    url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/assignments/'
            + str(ss['assignment_id']) + '/regrade_requests')
    driver.get(url)

    div_class_name = '.table--header.table--header-withFilter'
    
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    
    
    regrades = []
    # Need to determine whether grades have been released yet
    soup = BeautifulSoup(driver.page_source, 'lxml')
    grades_not_released = soup.find('div', class_='blankState')
    if grades_not_released is not None:
        return regrades

    try:
        table_element = WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "DataTables_Table_0"))
        )
    except TimeoutException:
        st.write("Timed out waiting for the table DataTables_Table_0 to become visible.") 
        
    # Get the info in the text of the regrades table
    table_html = table_element.get_attribute('outerHTML')  
    regrades_df = pd.read_html(StringIO(table_html))[0]
    
    # Grab the links to the regrade results, and store in regrades_df
    soup = BeautifulSoup(table_html, 'lxml') # was 'html.parser'
    links = [("https://www.gradescope.com" + a.get('href'))
             for a in soup.find_all('a', href=True)
             if 'Review' not in a.get_text(strip = True)]
    regrades_df['link'] = links
    regrades_df['submission_id'] = (regrades_df['link'].str.split('/').str[-1]).str.split('#').str[0]
    regrades_df['Q_short'] = 'Q ' + regrades_df['Question'].str.split(':').str[0]
    cols_to_drop = ['Sections','Completed','Review']
    regrades_df = regrades_df.drop(columns = cols_to_drop)
    regrades_df = regrades_df.sort_values(by = 'Student')

    submission_ids = regrades_df['submission_id'].unique().tolist()
    
    results = []
    for id in submission_ids:
        regrades_for_student_df = get_regrades_for_one_student(id)
        subdf = regrades_df[regrades_df['submission_id'] == id]
        merged_df = pd.merge(left = subdf, right = regrades_for_student_df, on = 'Q_short', how = 'left')
        results.append(merged_df)
    
    regrades_df = pd.concat(results, ignore_index = True)
    regrades_df['Submission_time'] = pd.to_datetime(regrades_df['Submission_time'], errors='coerce', utc = True)
    regrades_df['Submission_time'] = regrades_df['Submission_time'].dt.tz_convert('America/New_York')
    regrades_df['Submission_time'] = regrades_df['Submission_time'].dt.tz_localize(None)

    cols_to_drop = ['Q_short','submission_id']
    regrades_df = regrades_df.drop(columns = cols_to_drop)
    
    col_order = ['Student', 'Question', 'Grader', 'link', 'Student_comment', 'Grader_reply', 'complete', 'Submission_time']
    regrades_df = regrades_df[col_order]
    regrades_df = regrades_df.drop_duplicates() # This corrects an issue with students who submit a second request for the same question
    ss.regrades_df = regrades_df

def get_regrades_for_one_student(submission_id):

    driver = ss['driver']
    url = ('https://www.gradescope.com/courses/' + str(ss['course_id']) + '/assignments/'
            + str(ss['assignment_id']) + '/submissions/' + str(submission_id))
    driver.get(url)
    
    div_class_name = '.l-reactWrapper.notranslate'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.") 
        
    soup = BeautifulSoup(driver.page_source, 'lxml')   # was 'html.parser'
    
    element_with_props = soup.find('div', attrs={'data-react-class': 'AssignmentSubmissionViewer', 
                                                 'data-react-props': True})
    
    cols = ['Q_short', 'Submission_time', 'Student_comment', 'Grader_reply', 'complete']
    regrades_for_student_df = pd.DataFrame(columns = cols)
    if element_with_props:
        #st.code(element_with_props.prettify())
        props_json_string = element_with_props['data-react-props']
        data_props = json.loads(props_json_string)
        
        # Only needs to be done once.
        if ss.questionName_dict is None:
            questionName_dict = {}
            outline = data_props.get("outline")
            for parent_index, parent in enumerate(outline):
                parent_id = parent["id"]
                
                if "children" in parent:
                    for child_index, child in enumerate(parent["children"]):
                         child_id = child['id']
                         name = 'Q ' + str(parent_index + 1) + '.' + str(child_index + 1)
                         questionName_dict[child_id] = name
                else:
                    name = 'Q ' + str(parent_index + 1)
                    questionName_dict[parent_id] = name
            ss.questionName_dict = questionName_dict
        
        # question_dict maps id of students specific question to the general question id
        question_dict = {item['id']: item['question_id'] for item in data_props.get('question_submissions')}
        student_regrade_requests = data_props.get("regrade_requests")
        for request in student_regrade_requests:
            question = ss.questionName_dict[question_dict[request['question_submission_id']]]
            Submission_time = request['created_at']
            Student_comment = request['student_comment']
            Grader_reply = request['staff_comment']
            complete = request['completed']
            
            new_row_data =[str(question), Submission_time, Student_comment, Grader_reply, complete]
            regrades_for_student_df.loc[len(regrades_for_student_df)] = new_row_data
            
    # If a student submits a second regrade request for the same item, both requests appear twice. Avoid this by dropping duplicates.
    return regrades_for_student_df

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
                        EC.presence_of_element_located((By.XPATH, "//table[@id='DataTables_Table_0']"))
                    )
                except TimeoutException:
                    st.write("Timed out waiting for the table DataTables_Table_0 to become visible.") 
                    
                table_html = table_element.get_attribute('outerHTML')  
                rubric_item_df = pd.read_html(StringIO(table_html))[0]
                rubric_item_df.drop(columns=['Sections'], inplace=True, errors='ignore')
                
                # Convert the Graded time column to a proper datetime
                time_part = rubric_item_df['Graded time'].str.extract(r'^(.*?)\s*\(')[0].str.strip()
                full_datetime_str = str(ss.year) + ' ' + time_part.str.replace(" at ", " ")
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

    # Grab table of names from the submissions for one question
    table_html = table_element.get_attribute('outerHTML')  
    students_df = pd.read_html(StringIO(table_html))[0]
    ss['activity_df'] = students_df[['User']]
    ss['activity_df'].index += 1
    ss['activity_df'] = ss['activity_df'].rename(columns = {'User': 'Student\'s name'})
    ss['activity_df'] = ss['activity_df'].rename_axis(index="order")
    ss['activity_df'] = ss['activity_df'].reset_index()
    
    # While we are here, let's grab links to student papers
    soup = BeautifulSoup(table_html, 'lxml') # was 'html.parser'
    tds = soup.find_all('td', class_ = 'table--primaryLink')
    updates = {}
    for td in tds:
        a_tag = td.find('a')
        if a_tag and 'href' in a_tag.attrs:
            url = "https://www.gradescope.com" + a_tag['href']
            student_name = a_tag.get_text(strip = True)
            updates[student_name] = url
    for name, url in updates.items(): 
         ss.activity_df.loc[ss.activity_df["Student's name"] == name, "link"] = url
    
def process_the_assignment():
    """ After the user has selected a course and assignment, this function does all of the processing. """
    ss.downloaded_assignment = ss.selected_assignment   # Prevents problems upon page switching
    if 'driver' not in ss:
        GS_login()
    get_section_with_min_students()
    get_questions()
    get_students_in_order()
    get_all_rubric_items()
    get_assignment_data()
    ss.questionName_dict = None
    get_regrades_df()
    
    # Fix the year, particularly for Fall semester wher grading goes into January    
    cols = [col for col in ss.activity_df.columns if col.startswith('G time')]
    ss.activity_df[cols] = ss.activity_df[cols].apply(pd.to_datetime)
    fix_the_year(ss.activity_df, cols, ss.term, ss.year)
    if ss.regrades_df is not None:
        cols = ['Submission_time']
        ss.regrades_df['Submission_time'] = ss.regrades_df['Submission_time'].apply(pd.to_datetime)
        fix_the_year(ss.regrades_df, cols, ss.term, ss.year)       


def reset_contents():
    ss.activity_df = None
    ss.regrades_df = None 
    ss.questionName_dict = None   
        
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
    springEnd = datetime.strptime('May 20 2025', '%b %d %Y').date().replace(year=today.year)
    summerEnd = datetime.strptime('Aug 20 2025', '%b %d %Y').date().replace(year=today.year)
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
    
def get_year():
    """ Gets the term and year by looking on the dashboard """
    driver = ss.driver
    url = 'https://www.gradescope.com/courses/' + str(ss.course_id)
    driver.get(url)
    
    div_class_name = 'l-content'
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CLASS_NAME, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.")    

    soup = BeautifulSoup(driver.page_source, 'lxml')
    
    div = soup.find('h2', class_='courseHeader--term')
    if div is not None:
        term_year = div.text
    else:
        term_year = currentTerm()
    ss.year = int(term_year.split()[-1])
    ss.term = term_year.split()[0]
    st.write(ss.year, ss.term)

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

def get_section_with_min_students():
    """ Find the section with the minimum number of students to speed up Gradescope """
    driver = ss.driver
    url = 'https://www.gradescope.com/courses/' + str(ss.course_id) + '/sections'
    driver.get(url)
    
    div_class_name = '.l-reactWrapper.notranslate' 
    try:
        # Wait until the element with the specified class is visible
        visible_div = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, div_class_name))
        )
    
    except TimeoutException:
        st.write(f"Timed out waiting for the div with class '{div_class_name}' to become visible.") 
        
    ss.section_with_min_studentsID = None
    soup = BeautifulSoup(driver.page_source, 'lxml')

    blankState = soup.find('div', class_='blankState blankState-withSmallPadding')
    if blankState:
        return      # No section data
    
    element_with_props = soup.find('div', attrs={'data-react-class': 'CourseSections'})
    
    if element_with_props:
        props_json_string = element_with_props['data-react-props']
        data_props = json.loads(props_json_string)
        section_dict = data_props['sectionNameBySectionId']
        sectionID_dict  = {value: key for key, value in section_dict.items()}
    
    table_element = soup.find('table', class_ = 'table table-courseSections')
    if table_element:
        table_html = str(table_element)
        sections_df = pd.read_html(StringIO(table_html))[0]
        min_students_index = sections_df['Students'].idxmin()
        section_with_min_students = sections_df.loc[min_students_index, 'Section Name']
        ss.section_with_min_studentsID = sectionID_dict[section_with_min_students]

def fix_the_year(df, colList, term, year):
    """ Gradescope does not record the year in its dates, so we initially guess year from term.
            This causes a problem in the Fall, because late grading can go into January. Try to fix this """

    if term == 'Summer':
        startDate = pd.to_datetime('2000-05-20').replace(year=year)
    elif term == 'Fall':
        startDate = pd.to_datetime('2000-08-20').replace(year=year)
    else:
        return
    
    for col in colList:
        # Check if the date's month and day combination is before startDate
        mask = df[col].dt.to_period('D') < pd.Period(startDate, freq='D')
        
        # Fix any dates that are too early
        df.loc[mask, col] += pd.offsets.DateOffset(years=1)
    
def handle_course_change():
    """ Handles course selection change drop down. When the course changes, get a list
        of all assignments for that course and reset the assignment selector to none """
    ss.course_id = ss.course_dict[ss.selected_course]
    get_year()
    get_assignments(ss.course_id)
    ss.selected_assignment = None
    ss.assignment_id = None
    reset_contents()
    
def handle_assignment_change():
    """ Handles assignment selection change drop down """
    selected_assignment = ss.selected_assignment
    ss['assignment_id'] = ss.assignment_dict[selected_assignment]
    reset_contents()

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
if 'questionName_dict' not in ss:
    ss.questionName_dict = None
if 'activity_df' not in ss:
    ss.activity_df = None
if 'regrades_df' not in ss:
    ss.regrades_df = None
if 'section_with_min_studentsID' not in ss:
    ss.section_with_min_studentsID = None
if 'year' not in ss:
    ss.year = None
if 'term' not in ss:
    ss.term = None

st.title('Download Assignment Grading Data')

text_str = "Use the button below to log in to Gradescope. If you are NOT using automated password login,  "
text_str += "you will have 3 min to complete the login in the browser window after you push the button. "
text_str += "In either case, leave the browser window open after you finish logging in."
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
#         index = None,                # Always start at none selected
        on_change = handle_course_change
    )
    
if ss['assignment_dict'] is not None:
    st.selectbox(
        'Select an assignment', # Label for the dropdown
        options = list(ss['assignment_dict'].keys()), # The options to display
        key = 'selected_assignment',
#         index = None,                # Always start at none selected
        on_change = handle_assignment_change
    )

if ss.course_id is not None and ss.assignment_id is not None:
    text_str = 'After pushing the button, the script will loop through the assignment in Gradescope, '
    text_str += 'finding all of the rubric items. It will then loop through each rubric item and '
    text_str += 'record the grading activity associated with that item. If there have been any regrades, '
    text_str += ' their data will be downloaded. At the end, you will be '
    text_str += 'given the opportunity to save the grading data to an Excel file for analysis.'
    st.write(text_str)
    text_str = 'The slowest part of this process is often Gradescope\'s calculation of the assignment statistics, '
    text_str += 'which we try to speed up by only looking at the smallest section.'
    st.write(text_str)
    if st.button("Start Downloading", type = 'primary'):
        status_placeholder = st.empty()
        start_time = time.perf_counter()
        status_placeholder.write("Downloading in progress...")
        process_the_assignment()
        end_time = time.perf_counter()
        elapsed_time = (end_time - start_time)/60
        status_placeholder.write(f"Elapsed time: {elapsed_time:.1f} min")

if ss.activity_df is not None:
    
    st.write('### All grading activity')
    st.dataframe(ss['activity_df'], 
                 column_config={"link": st.column_config.LinkColumn("link", display_text="link")},
                 hide_index = True)
    
    st.write('### All regrading activity')
    text_str = 'If the text in a cell is too long to read, double-click for a better view.'
    st.write(text_str)
    if 'regrades_df' in ss:
        st.dataframe(ss['regrades_df'],
                        column_config={"link": st.column_config.LinkColumn("link", display_text="link")},
                        hide_index=True, row_height=110)

    text_str = 'You can save the data '
    text_str += 'as separate sheets of a single Excel file in your downloads folder '
    text_str += 'using the button below. This avoids the need for multiple csv\'s'
    st.write(text_str) 
    if st.button('Download to Excel', type = 'primary'):
        twoWords = ss.downloaded_assignment.split()[:2] # Use first two words of assignment
        shortAssignmentName  = "_".join(twoWords) 
        file_name = '~/Downloads/GS_activity_' + shortAssignmentName + '_' + datetime.now().strftime("%b_%d") + '.xlsx'
        with pd.ExcelWriter(file_name, mode = 'w',engine='xlsxwriter') as writer:
            # Write each dataframe to a different worksheet
            ss.activity_df.to_excel(writer, sheet_name='Grading', index=False)
            if ss.regrades_df is not None:
                ss.regrades_df.to_excel(writer, sheet_name='Regrading', index=False)

                    
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
