# Ski & Snowboard Team Dashboard

A modern, full-featured operations and treasury dashboard designed for collegiate ski and snowboard teams, club sport officers, and team treasurers. Built with Python and Streamlit, featuring an alpine dark theme, dual blue accents, comprehensive financial tracking, roster management, trip logistics, and officer collaboration tools.

---

## Quick Start (Local Run)

1. **Activate Virtual Environment:**
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. **Configure Secrets (Optional for Officers):**
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
   - Set your custom `OFFICER_PASSWORD` and private `MEMBERSHIP_FORM_SHEET_URL`.
3. **Run Streamlit Application:**
   ```powershell
   streamlit run app.py
   ```
4. Open your browser at `http://localhost:8501`.

---

## Access Modes and Security Controls

The dashboard provides a dual-layer security architecture designed for both public demonstration and internal officer operations:

- **Demo Mode (Default):**
  - Designed for public presentations, portfolio showcases, and prospective member browsing.
  - Automatically loads realistic mock data across all 8 modules.
  - Keeps all live club records, financial receipts, and member contact info completely hidden.
- **Officer Mode:**
  - Unlocked by entering the officer password in the sidebar.
  - Instantly transitions the dashboard to read and manage live team datasets.
- **Sidebar Editing Toggle:**
  - When logged in as an officer, a dedicated toggle switch appears in the sidebar: **Enable Editing Mode**.
  - **Editing Active:** Officers can create trips, log transactions, sync Google Forms, adjust merch stock, assign tasks, and edit data in real time.
  - **Viewing Only (Locked):** Officers can inspect live team records while editing forms, table inputs, delete buttons, and status modifiers are locked to prevent accidental modifications during meetings.

---

## Core Modules and Features

### 1. Financial Overview and Season KPIs
- **Real-Time Financial Metrics:** Instant calculation of Total Treasury Balance, Total Season Revenue, Total Season Expenses, and Net Operating Margin.
- **Monthly Cash Flow Trend:** Interactive Plotly line charts displaying income vs expenses over time in dark mode.
- **Expense Category Distribution:** Color-coded donut and bar charts breaking down expenditures across Lodging, Lift Tickets, Transportation, Gas, Socials, Race Fees, Merch, and Administrative costs.
- **Multi-Season Filtering:** Toggle between the active academic year, historical seasons, or an aggregate view across all years.
- **Dynamic Cash Flow Insights:** Contextual warnings and indicators reflecting team liquidity and budget burn rate.

### 2. Financial Ledger and Officer Entry Portal
- **Interactive Spreadsheet Editor:** Full spreadsheet grid with direct cell editing for dates, entities, categories, dollar amounts, notes, and academic seasons. In-table edits persist immediately to the database.
- **Officer Transaction Entry Form:** Rapid expense and revenue logging with automatic category categorization, entity specification, and season tagging.
- **Comprehensive Filtering & Search:** Real-time multi-field search across vendor names and transaction descriptions, alongside transaction type and category filters.
- **Audit-Ready CSV Export:** One-click download of filtered or full ledger records formatted for club sports compliance, student government audits, and spreadsheet archives.
- **Treasurer Transaction Management:** Secure single-transaction deletion with full record preview and row verification.

### 3. Membership and Registration Tracker
- **In-Table Interactive Controls:** Directly click checkboxes inside the table grid to toggle **Dues Paid** ($60) and **Comp Team** (USCSA racers).
- **T-Shirt Size Management:** Dropdown selection for standard sizes (None, S, M, L, XL), dynamically linked to the team merch inventory pool.
- **Full Athlete Profiles:** Tracks primary discipline (Ski, Board, Both), Academic Year, Slack onboarding status, Phone Number, Email Address, Trips Attended, and Google Form notes.
- **Google Forms Live Sync & CSV Import:** Automated 1-click sync connecting the team registration Google Sheet or uploading an exported Google Form CSV.
- **Roster Management & Multi-Member Actions:** Manual athlete registration form, search filtering, and single or bulk member deletion with automated dues reconciliation.
- **Season Transition & Archiving Tool:** Roll forward to a new academic year with a single click while permanently archiving past rosters for historical lookup.

### 4. Merch Inventory and Distribution Tracker
- **Dual Inventory Pool Monitoring:**
  - **T-Shirts:** Tracks baseline stock across S, M, L, and XL sizes.
  - **Sweatshirts / Hoodies:** Tracks baseline stock across S, M, L, and XL sizes.
- **Automated Dynamic Deductions:** Claimed t-shirt sizes from the Membership Tracker automatically decrement available stock in real time.
- **Independent Gear Logger:** Record outside sales, officer apparel distributions, alumni orders, or warehouse restocks.
- **Visual Stock Breakdowns:** Plotly bar charts visualizing remaining available units versus claimed or distributed units per size.
- **Transaction Audit Log:** Complete historical log of all independent adjustments with reversible deletion and inventory recalculation.

### 5. Monthly Calendar and Master Schedule
- **Dual View Modes:** Seamlessly switch between an interactive **Monthly Calendar Grid** and a detailed **Master Schedule Table**.
- **Interactive Monthly Calendar:**
  - Dynamic navigation buttons (Previous Month, Next Month, and Today).
  - Multi-day event spanning with distinct color coding across event categories:
    - Ski Trips
    - Club Meetings
    - Social Events
    - Races & Competitions
    - Workouts & Dryland Training
    - Fundraisers
  - Clickable date badge indicators that open modal event detail inspectors showing times, locations, and descriptions.
- **Master Schedule Table with In-Place Editing:**
  - Direct in-table editing of event names, event types, start/end dates, start/end times, locations, and descriptions.
  - Filter by event type or search by keyword across all upcoming dates.
- **Event Scheduler:**
  - Create new club meetings, socials, races, workouts, or custom events with date pickers, time selectors, and custom location entry.
- **1-Click Google Calendar Integration:**
  - Instant pre-filled Google Calendar links that automatically convert dates, times, descriptions, and locations into ready-to-save calendar events.
- **iCalendar (.ics) Export:**
  - Export the complete master schedule or individual events to standard `.ics` format, compatible with Apple Calendar, Google Calendar, and Microsoft Outlook.

### 6. Trip Creator and Operations Manager
- **Trip Operations & Attendee Tracker:**
  - Dedicated attendee rosters per trip with in-table **Payment Received** checkboxes.
  - Driver capacity tracking with automatic seat summation.
  - Searchable active member dropdown ensuring only registered club members are added to official trip rosters.
  - Individual or bulk attendee removal with automated trip count updates.
- **Driver Sign-Up Sheet Generator (Google Apps Script):**
  - Generates a custom Google Apps Script in one click.
  - When executed, creates a formatted Google Sheet in Google Drive containing:
    - Confirmed driver names and phone numbers.
    - Verified passenger capacity.
    - Open passenger sign-up slots.
    - Automated red cell fills for slots that exceed a driver's vehicle capacity.
- **Trip Google Form Live Sync:**
  - Connect a trip-specific Google Form response sheet or upload response CSVs to auto-populate attendee rosters.
- **Full Trip Builder:**
  - Built-in mountain destination presets with automatic mileage and default night calculations.
  - Comprehensive budget breakdowns: Cabin Lodging, Food & Drink, Fuel / Gas, and Lift Tickets.
  - Automated per-person ticket pricing calculation.
  - Automated Google Form Sign-Up Generator script tailored to the trip specifications.
- **Trip Status & Lifecycle Management:**
  - Update status through Planning, Confirmed, Completed, and Cancelled states.
  - Complete trip deletion with cascaded attendee cleanup.

### 7. Trip Cost Estimator
- **Interactive Budget Forecasting:** Calculate trip costs based on departure origin, distance, nights of lodging, attendees, and vehicle counts.
- **Granular Expense Models:** Separate budget inputs for cabin rental, food and beverage, lift tickets, and vehicle fuel.
- **Fuel Consumption Modeling:** Estimates fuel expense using round-trip mileage, average vehicle MPG, current fuel prices, and seat occupancy.
- **Per-Skier Pricing & Club Subsidies:** Instant break-even pricing per attendee with adjustable club subsidy sliders.

### 8. Officer Task Delegation and To-Do List
- **Task Assignment & Role Delegation:** Assign action items to one or multiple executive board members (President, Treasurer, Trip Director, Social Chair, Gear Manager, etc.).
- **Deadline Tracking:** Set target completion dates, request submission timestamps, priority indicators, and detailed instructions.
- **Active Task Management:** Filter active tasks by assigned officer, inspect detailed descriptions, and move tasks to the archive via **Mark Completed**.
- **Archive of Completed Tasks:** Historical record of completed team tasks with completion timestamps and the ability to re-open tasks if further action is needed.

---

## Google Workspace Integration Ecosystem

The dashboard is engineered to integrate natively with standard Google Workspace tools used by collegiate clubs:

- **Google Forms & Sheets:** Bi-directional sync for general club registration and trip-specific athlete sign-ups.
- **Google Apps Script:** Automated generation of customized Google Forms and formatted carpool spreadsheets directly within the user's Google Drive.
- **Google Calendar:** Pre-formatted calendar links for one-click event creation across all team activities.

---

## Technical Stack and Architecture

- **Frontend & App Framework:** Streamlit
- **Data Manipulation:** Pandas & NumPy
- **Interactive Visualizations:** Plotly Express & Plotly Graph Objects
- **Calendar & Time Operations:** Python `datetime`, `calendar`, and `ics`
- **Data Storage:** Structured CSV database with automated schema initialization and isolated demo environments
- **Theme:** Alpine Dark (#0e131f base, #171f30 secondary, #5d6895 primary slate blue, #8b9bb4 periwinkle highlight)

---

## Project Structure

```
.
├── app.py                     # Main application entry point and sidebar controls
├── config.py                  # Global configuration, destination presets, and constants
├── modules/
│   ├── financials.py          # Financial Overview and KPI charts
│   ├── ledger.py              # Financial Ledger and Officer Entry Portal
│   ├── registration.py        # Membership and Registration Tracker
│   ├── merch.py               # Merch Inventory and Distribution Tracker
│   ├── calendar_view.py       # Monthly Calendar and Master Schedule
│   ├── trip_creator.py        # Trip Creator and Operations Manager
│   ├── trip_estimator.py      # Trip Cost Estimator
│   └── todo.py                # Officer Task Delegation and To-Do List
├── utils/
│   ├── data_manager.py        # Data loading, persistence, and Google sync utilities
│   └── sample_generator.py    # Realistic demo data generation
├── data/                      # Live team data files (CSV)
│   └── demo/                  # Public demo data files (CSV)
└── assets/                    # Team branding and logo assets
```
