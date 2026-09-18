# Project State & Developer Handoff

## Current Status & Architecture
The UCSB Ski & Snowboard Team Dashboard is a production-ready web application built with **Python 3.13+**, **Streamlit (1.64.0)**, **Pandas**, and **Plotly**. The application entrypoint is [[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)], which orchestrates a persistent dark UI (`#0e131f`, `#171f30`) accented with the team's signature two blues (`#33406a`, `#5d6895`), role-based access control (public view-only vs. officer unlocked mode), and client-side DOM controllers. The interface features a persistent sidebar housing team branding, a global season selector (`2026-2027`, `2025-2026`, `All Seasons`), an officer passcode gate (configured securely via Streamlit secrets), and single-page radio navigation spanning seven dedicated functional modules.

---

## Completed Components & Features

### Core Application & Routing
- **Entrypoint & Navigation** ([[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)]):
  - Sidebar navigation switching between 7 modules: *Financial Overview*, *Ledger and Officer Entry*, *Membership Tracker*, *Merch Tracking*, *Trip Creator*, *Trip Budget Estimator*, and *Officer To-Do & Archive*.
  - Global Season Selector with dynamic seasonal filtering passed to all modules.
  - Subfolder resolution fallback logic ensuring seamless deployment on Streamlit Cloud regardless of repository nesting.
- **Access Control & Passwordless UX** ([[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)]):
  - Officer passcode verification (managed securely via Streamlit secrets and `st.session_state['is_officer']`).
  - Non-password input field (`st.text_input` without `type="password"`) paired with a direct button, completely preventing browser password managers ("Save password?" / key icon prompts) and removing the browser combobox username heuristic on "Viewing Season".
  - Universal CSS suppression of Streamlit form submit prompts (`[data-testid="InputInstructions"] { display: none !important; }`).
- **Dropdown Keyboard Lockdown** ([[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)]):
  - Custom JavaScript controller injected via `streamlit.components.v1.html` applying `readOnly = true` and `readonly="true"` across all `st.selectbox` and `st.multiselect` inputs (`[data-testid="stSelectbox"]`, `[data-testid="stMultiSelect"]`, `.react-aria-ComboBox`).
  - Active `MutationObserver` automatically detecting and locking newly mounted dropdowns when users navigate across tabs or add data rows.
  - Capturing-phase event interceptor blocking `keydown`, `keypress`, and `beforeinput` character insertions while preserving keyboard navigation (`Tab`, `Escape`, `Enter`, Arrow keys).
  - Python-level monkey-patching defaulting `filter_mode=None` to ensure `inputMode: "none"` on mobile devices.
  - CSS styling enforcing `caret-color: transparent !important;` and `cursor: pointer !important;`.
  - **Targeted Exception for Member Search**: Typing and fuzzy searching are explicitly enabled exclusively for the "Select Active Member (Searchable)" dropdown in Trip Operations, allowing officers to type and search across club athlete rosters while keeping all other dashboard dropdowns securely locked.

### Data Pipelines & Configuration
- **Central Configuration** ([[config.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/config.py)]):
  - Constants for team officers, current season, destination presets with round-trip mileages (Mammoth, Bear Valley, China Peak, Big Bear, Palisades), vehicle consumption rates (20 MPG, $4.85/gal, 4 skiers/vehicle), competition travel rate ($0.70/mile), baseline merch inventory, and financial ledger categories.
- **Data Engine** ([[utils/data_manager.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/utils/data_manager.py)]):
  - Atomic read/write functions for local CSV storage in [[data/](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/data)]: `ledger.csv`, `members.csv`, `merch_adjustments.csv`, `todos.csv`, `trips.csv`, and `trip_signups.csv`.
  - Financial KPI aggregation (`get_financial_kpis`) calculating total income, total expenses, net balance, and seasonal breakdowns.
  - Live Google Sheets CSV import pipeline with header normalization and fallback schema seeding.

### Functional Modules
- **Financial Overview** ([[modules/financials.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/financials.py)]):
  - KPI summary metric cards (Total Revenue, Total Expenses, Net Margin, Current Cash Balance).
  - Monthly Cash Flow Trend bar chart (Income vs. Expense) displaying up to 12 months in strict season order starting with September (Sep -> Aug), completely omitting months with no flows.
  - Multi-season Cash Flow by Season view: When 'All Seasons' is selected, compares expenses and income side-by-side grouped by season.
  - Distribution doughnut charts breaking down revenue streams and expense categories.
  - Recent transactions audit trail.
- **General Ledger & Officer Entry** ([[modules/ledger.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/ledger.py)]):
  - View-only formatted transaction table for general club members.
  - Officer interactive in-place editable grid powered by `st.data_editor` allowing direct updates to all fields (Date, Season, Type, Category, Amount, Description, Logged By).
  - Single transaction entry form with category selectors and officer attribution.
  - **Google Sheets Live Sync & CSV Ledger Backup**: Dedicated expander enabling officers to synchronize the master ledger directly with a private Google Sheet (`LEDGER_SHEET_URL`), import/restore CSV backups, or download the full master ledger across all seasons with 1 click.
  - **Cold-Boot Cloud Persistence**: Automatically populates `data/ledger.csv` directly from `LEDGER_SHEET_URL` on Streamlit Community Cloud reboots if the container disk starts empty.
  - Record deletion utility with confirmation dialogs.
- **Membership & Dues Tracker** ([[modules/registration.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/registration.py)]):
  - Member table with multi-parameter filtering: Search Roster (by Name, Email, Notes, Trips, Year, Ski/Board), Season, Dues Paid/Unpaid, Slack Status (`All`, `In Slack Only`, `Not in Slack`), Ski/Board (`All Disciplines`, `Ski`, `Board`, `Both`), Shirt Size, and Team Division.
  - Interactive roster grid powered by `st.data_editor` with optimized column ordering (`Name`, `Year`, `Ski/Board`, `Slack`, `Dues Paid`, `Comp Team`, `T-Shirt Size`, `Email`, `Phone`, `Trips Attended`, `Notes`, `Season`, `ID`), making academic year, discipline, and Slack status immediately visible without horizontal scrolling. Dedicated column configurations: `Year` text column, `Ski/Board` selectbox (`Ski`, `Board`, `Both`), and `Slack` checkbox column.
  - Direct member registration form with Academic Year selector (`1`, `2`, `3`, `4`, `Grad`, `Other`), Ski or Board selector (`Ski`, `Board`, `Both`), Joined Slack checkbox, and Comp Team defaulted to `False`.
  - Live sync tool fetching registration responses from the official Google Sheets form (*"UCSB Ski and Board Team Member Applications 26-27"*), automatically extracting and mapping `"What year are you?"` -> `Year` (with integer cleanup) and `"Do you ski or board?"` -> `SkiBoard` (`Ski`, `Board`, `Both`), leaving `Slack` defaulted to `False` and `CompTeam` defaulted to `False` with completely severed/no link to form input data.
  - Member deletion utilities: Bulk or single deletion via the 'Delete Member from Roster' expander with searchable multiselect, as well as an in-line 'Delete a Member' popover below the table. Automatically cleans up member records in `members.csv`, revokes associated dues payment entries from `ledger.csv`, and cleans up active trip signups in `trip_signups.csv`.
  - Dynamic Trips Attended Synchronization: Integrates automatic ingestion reconciliation in `load_members()` ensuring every member's `TripsAttended` accurately reflects registered trips from `trip_signups.csv` and `trips.csv` (`AttendeeRoster`) strictly scoped to their active season, eliminating cross-season contamination for returning athletes while preserving uncataloged historical trips.
  - Officer quick-actions: toggle dues payment status, toggle Slack status checkbox, toggle Comp Team status checkbox, and edit member info directly in `st.data_editor`.
- **Merch Inventory Tracking** ([[modules/merch.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/merch.py)]):
  - Real-time inventory calculation: Initial Stock minus Distributed T-Shirts (from registered members) plus/minus manual adjustments.
  - Inventory breakdown cards for T-Shirts and Sweatshirts across all sizes (S, M, L, XL).
  - Adjustment logging system (Sale, Restock, Damage, Giveaway, Correction) with officer attribution.
  - Historical adjustment audit log.
- **Trip Creator & Operations** ([[modules/trip_creator.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/trip_creator.py)]):
  - Trip creation workflow supporting Recreational and Competition trips.
  - Automated Competition Trip Roster: Creating a `Competition` trip automatically identifies all active members on the Competition Team (`CompTeam == True`), adds them to the trip's `AttendeeRoster`, registers them in `trip_signups.csv`, synchronizes their `TripsAttended` history in `members.csv` for the matching season, and automatically adjusts trip expected attendees to accommodate all competitors.
  - Full Bidirectional Roster Sync: Adding attendees (`add_trip_attendee`), syncing form sheets (`parse_and_sync_trip_form_df`), deleting attendees (`delete_multiple_trip_attendees`), or deleting entire trips (`delete_trip`) maintains 100% real-time synchronization between `trips.csv` (`AttendeeRoster`), `trip_signups.csv`, and `members.csv` (`TripsAttended`).
  - Automated budget estimation based on resort distance, gas pricing, lodging, and lift tickets.
  - Built-in Google Form Sign-Up Generator with dynamic add/delete/edit response fields via `st.data_editor`, dedicated field creation popovers, field removal, and default reset.
  - 1-Click Google Apps Script generator producing customized code matching athlete question fields, formats, and choices.
  - Seamless post-creation workflow automatically collapsing both Section 1 (Trip Details & Budget Logistics) and Section 2 (Built-in Google Form Sign-Up Generator) while automatically expanding the 1-Click Google Apps Script code with a prominent success banner, and providing a 1-click 'Create Another Trip' reset action.
  - Robust Attendee Tracker with in-table editing via `st.data_editor` featuring strict type sanitization (preventing `StreamlitAPIException` on empty questions/floats), fuzzy searching exclusively for registered active members, payment checkboxes, driver capacity dropdowns, and multi-attendee removal.
  - Automatic Ledger Integration: toggling the `Payment Received` checkbox creates a corresponding Income `Trip Payment` entry in the General Ledger (calculated from trip cost per skier), and unchecking it removes the entry, functioning identically to the membership dues checkbox.
  - Streamlined Operations Metrics: Clean KPI cards displaying Total Attending Athletes, Trip Cost per Person, Driver Capacity Available, and Pending Payments without noisy delta insights.
  - Interactive Trip Status Management: Added Trip Status dropdown selectors to both the Trip Operations Details card (Tab 1) and each individual Trip Details Card in All Scheduled Trips (Tab 3). Allows officers to easily toggle trip statuses (`Planning`, `Confirmed`, `Completed`, `Cancelled`) with in-place persistence to `trips.csv` via `update_trip_status()`. Locked with tooltips in view-only mode.
  - 1-Click iCalendar (.ics) Export: Added a calendar export feature on the All Scheduled Trips overview tab. Generates an RFC 5545 compliant `.ics` file containing all scheduled trips (or filtered trips) with accurate date ranges, all-day exclusive DTEND calculations, location, and status. The event description cleanly displays only trip, type, destination, dates, and status (excluding financial data and attendee counts), seamlessly importable into Apple Calendar, Google Calendar, and Microsoft Outlook.
  - 1-Click Driver Sign-Up Sheet Generator (Google Apps Script): Added functionality to the Trip Manager (Tab 1) that generates Google Apps Script code to create a styled Google Sheet for driver carpools with the exact 8 columns: `Driver`, `Phone Number`, `# of Passengers`, `Departure Time`, `Passenger 1`, `Passenger 2`, `Passenger 3`, `Passenger 4`. Automatically filters for attendees who signed up to drive (capacity >= 1), populates their phone numbers and capacities, leaves passenger columns blank, and fills unavailable passenger cells with a distinct red background (`#ea4335`). Accessible via a dedicated expander with live capacity preview metrics and a quick popover in the roster Action Bar with `.js` script download.
- **Trip Budget Estimator** ([[modules/trip_estimator.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/trip_estimator.py)]):
  - What-if scenario calculator estimating total and per-person trip expenses.
  - Adjustable variables: resort destination, vehicle capacity, gas prices, lodging costs, and ticket fees.
- **Officer To-Do & Delegation** ([[modules/todo.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/todo.py)]):
  - Task board tracking pending, in-progress, and completed tasks.
  - Task assignment to one or more officers using multiselect tags.
  - Officer-specific view filtering and completed task archive.

---

## In-Progress & Next Steps

1. **GitHub Deployment Synchronization**:
   - Changes in [[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)] must be committed to the GitHub repository to update the live Streamlit Community Cloud instance.
2. **Google Sheets Service Account Auth (Optional)**:
   - Registration sync currently relies on public CSV publication. If the Google Sheet is set to restricted access, integrate Google Sheets API v4 using `gspread` or `google-auth` with credentials stored in `.streamlit/secrets.toml`.
3. **Cloud Object Storage for Receipts**:
   - Currently, receipts are logged as URL links (Google Drive / Dropbox). A direct file uploader storing images to AWS S3, Google Cloud Storage, or Supabase Storage can be added to the ledger module.
4. **Streamlit Future Syntax Cleanups**:
   - Replace legacy `use_container_width=True` on buttons and images with `width="stretch"` in accordance with Streamlit 2026 deprecation notices.

---

## Known Issues & Technical Debt

- **Ephemeral Storage on Streamlit Cloud & Persistent Google Sheets Architecture**:
  - Local CSV files in `data/` persist between sessions on local machines, but Streamlit Community Cloud instances reboot periodically. To protect data privacy while guaranteeing persistence, the sensitive club records (Master Financial Ledger and Membership Roster) persist via private Google Sheets (`LEDGER_SHEET_URL` and `MEMBERSHIP_FORM_SHEET_URL`) configured through Streamlit Secrets, ensuring zero sensitive financial data is stored in the public GitHub repo.
- **Streamlit Selectbox Native ReadOnly Gap**:
  - Streamlit currently lacks an official `read_only=True` parameter on `st.selectbox`. The app utilizes a client-side JavaScript injection (`streamlit.components.v1.html`) and `MutationObserver` alongside `filter_mode=None` to guarantee non-editable dropdown behavior.
- **Single Passcode Authorization**:
  - All officers share a team passcode managed securely via Streamlit secrets (`OFFICER_PASSWORD`). If individual officer accountability is required, migrate to a hashed multi-user table or Streamlit-Authenticator.

---

## Key Files Reference

| File | Description |
| :--- | :--- |
| [[app.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/app.py)] | Main application entrypoint, theme styling, passwordless login, and dropdown controller. |
| [[config.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/config.py)] | Global constants, officer lists, trip destinations, and theme color codes. |
| [[utils/data_manager.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/utils/data_manager.py)] | Data access layer, CSV I/O, Google Sheets sync, and financial KPI computations. |
| [[modules/financials.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/financials.py)] | Financial Overview view with Plotly cash flow and expense distribution charts. |
| [[modules/ledger.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/ledger.py)] | General Ledger table, editable data grid (`st.data_editor`), and CSV transaction upload. |
| [[modules/registration.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/registration.py)] | Membership roster, dues tracking, shirt size auditing, and Google Form synchronization. |
| [[modules/merch.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/merch.py)] | Real-time apparel inventory ledger, size matrices, and adjustment logs. |
| [[modules/trip_creator.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/trip_creator.py)] | Trip creation, roster building, vehicle/driver assignment, and attendance billing. |
| [[modules/trip_estimator.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/trip_estimator.py)] | Interactive cost modeling tool for upcoming mountain trips. |
| [[modules/todo.py](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/modules/todo.py)] | Officer task allocation, priority management, and task archives. |
| [[requirements.txt](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/requirements.txt)] | Python dependency manifest. |
| [[.streamlit/config.toml](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/.streamlit/config.toml)] | Streamlit client configuration and theme defaults. |
| [[data/](file:///c:/Users/bosqu/OneDrive/Documents/Ski%20Team%20Dash/data)] | Local CSV storage directory containing all database tables. |
