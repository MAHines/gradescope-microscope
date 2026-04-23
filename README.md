# Gradescope Microscope
## A Streamlit package for the analysis of grading in Gradescope 

<div align="center">
    <img src="assets/Gradescope_microscope.png" alt="Gradescope Microscope logo" style="width: 25%;">
</div>

This package downloads the entire grading history of a Gradescope assignment and then provides tools
for its analysis on either a course-wide or grader-by-grader basis.

This package uses Selenium, a framework for automating web browsers.

The workflow for analyzing all of the grading in a course is:

1. Make Assigned Activities for course (once per semester)

2. Download Gradescope Results for each graded item and store Grader Activity in Microscope Archive

3. Analyze Grader Activity for each graded item and store Daily Grading Report in Microscope Archive

4. Combine all Daily Grading Reports with Assigned Activities

### Download Gradescope Results

This module allows the user to log in to Gradescope "manually," using either SSO authentication 
or a stored password. The user then selects a course and an assignment in that course using
dropdown menus, as illustrated below.  

<div align="center">
    <img src="assets/Assignment_selection.png" alt="Table of estimated grading times" style="width: 60%;">
</div>

After the "Start Downloading" button is pushed, the script loops through the assignment
in Gradescope, finding all of the rubric items. The script then loops through each rubric item
and records the grading activity associated with that item. Once complete, the user is given the opportunity
to save the grading data in a csv for analysis with "Analyze Grader Activity."

This module (and the next one) also show all regrade activity, including student requests and grader
replies. These are presented in an easy to scan format as shown below.  

<div align="center">
    <img src="assets/Regrade_comments.png" alt="Table of all regrade requests" style="width: 95%;">
</div>

At the end of this process, you will be given an option to either Save to Excel (old method) or
**Archive to Excel** (preferred). I strongly suggest the latter.

Your results will be stored in an autonamed file something like 'GS_Iron_Complex_Apr_15.xlsx'
where 'Apr_15' is today's date and 'Iron_Complex' is the first two words of the assignment name.

The location of your Microscope archive is set in Settings. On a Mac, the root folder of your
Microscope archive is likely ~/Documents/Microscope/. Each course will be stored in subfolders
whose names are derived from your Gradescope course, e.g., ~/Documents/Microscope/Chem2070/2026Spring/.

There is also an option to download the Evaluations Folder for analysis with "Analyze Grades."  

### Analyze Grader Activity  

This module analyzes the grading activity downloaded from Gradescope using the 'Download Gradescope
Results' script. Select the grader activity file, which should be stored in your Microscope Archive
and named something like 'GS_Iron_Complex_Apr_15.xlsx' where 'Apr_15' is today's date and
'Iron_Complex' is the first two words of the assignment name. An estimate of the time each
grader spent grading will then be calculated, as shown below.

<div align="center">
    <img src="assets/Grading_time.png" alt="Table of estimated grading times" style="width: 95%;">
</div>

The grading and regrading data are also presented in an easy to read histogram for the entire class
and on a grader-by-grader basis.

<div align="center">
    <img src="assets/Grading_Histogram.png" alt="Histogram of grading and regrading times" style="width: 80%;">
</div>

This module also identifies papers that had multiple graders. This can be useful for catching 
unauthorized grading if each paper is supposed to be graded (and regraded) by a single grader. The script
can also be used to analyze an individual grader's behavior, which can be useful in understanding
slow graders or awkward rubrics.

After analyzing the activity, you will be given the option to save your analysis to your Microscope
Archive in a file autonamed something like DailySum_GS_Iron_Complex_Apr_15.xlsx.

### Combine Daily Grading Reports

This module combines all of the Gradescope grading analyses with the TA's assigned times (e.g., for labs, OHs, 
class, TA meetings, and proctoring) to calculate the actual amount of time each TA spends on 
a class every week. The TA-by-TA output is displayed graphically, as shown below.  

<div align="center">
    <img src="assets/Weekly_Summary.png" alt="Histogram of TA grading times" style="width: 80%;">
</div>

Before using this script, you must make an Assigned Activity csv using the 'Make Assigned Activities
Sheet' script. I suggest storing the csv in the appropriate folder of your Microscope Archive.
You only need to do this once per semester. The root of your Microscope Archive is set in Settings.
On a Mac, the archive for a course will be something like ~/Document/Microscope/CHEM2070/2026Spring.

If you would like to save your output, I suggest using Print > Save as PDF in your browser. 
Make a special paper size (e.g., US Long) that is 8.5" x 110". This will allow you to save the
report as a long pdf with no annoying page breaks.

### Make Assigned Activities Sheet

This module is used to make a single-page spreadsheet that contains all of the activities assigned
to a TA and their duration (not including grading). These data are needed for the 'Combine Daily
Grading Reports' script. The actual day of the week assigned to each activity is irrelevant,
because we track time on a weekly basis.

<div align="center">
    <img src="assets/Assigned_Activity.png" alt="Histogram of Assigned Activity" style="width: 80%;">
</div>

After downloading the csv to your Downloads folder, you need to move it to the appropriate folder
in your Microscope Archive. The location of your archive is set in Settings. On a Mac, the root
folder of your Microscope archive is likely ~/Documents/Microscope/. Each course will be stored
in subfolders whose names are derived from your Gradescope course, 
e.g., ~/Documents/Microscope/Chem2070/2026Spring/.

### Analyze Grades

This module analyzes grading stored in a folder of Gradescope scores for an assignment, producing a grader-by-grader analysis as shown below.  

![Sample grading graph](assets/Grading_Report.png "Sample Grading Report")

To perform the analysis, download the Evaluations Folder with "Download Gradescope Results" (or mannualy).
Drag the resulting folder from your Downloads folder onto "Drag and drop files here."
Give the analysis a name in the modal dialog. An analysis of all problems will appear.  

To analyze a single problem, use the dropdown menu in the sidebar to select it.

### Update Gradescope Credentials  

If you use a username and password to log in to Gradescope, you can store them in your system keychain  
using this module. There is no need to do this if you prefer to log in manually.

### Settings  

This module allow certain user settings to be stored in prefs.toml in the .streamlit folder

### Installation
– Use Anaconda and pip install to make an env contains the following packages:  
  
    beautifulsoup4  
    keyring  
    numpy
    openpyxl  
    pandas  
    plotly  
    selenium  
    streamlit  
    tomlkit
    XlsxWriter  
 
– cd to the folder that will contain Gradescope Microscope  
– git clone https://github.com/MAHines/Gradescope-Microscope.git   

### Running Gradescope Microscope from the command line
– cd to Gradescope-Microscope folder  
– streamlit run microscope.py  

### Updating Gradescope-Microscope from the command line
– cd to Gradescope-Microscope folder  
– git pull  

