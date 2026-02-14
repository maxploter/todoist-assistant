# Todoist Assistant

A simple automation tool that organizes your Todoist tasks based on rules.

## Features

### Story 1: English Word Rule
When you add a task to Todoist Inbox with a title starting with "english" (case-insensitive), it automatically moves to the "english-words" project.

**Examples:**
- ✅ `English: apple` → moves to english-words
- ✅ `english word: banana` → moves to english-words
- ✅ `ENGLISH test` → moves to english-words
- ❌ `Learn english` → does NOT move (doesn't start with "english")

### Story 2: Automated Daily Runs
The assistant runs automatically every day at 7pm UTC via GitHub Actions.

## Setup

### 1. Prerequisites
- A Todoist account
- A GitHub account (for automated runs)
- Python 3.11+ (for local testing)

### 2. Create the "english-words" Project in Todoist
Before running the assistant, make sure you have a project named `english-words` in your Todoist account.

### 3. Get Your Todoist API Token
1. Go to https://todoist.com/app/settings/integrations/developer
2. Scroll down to "API token"
3. Copy your token

### 4. Local Setup (Optional - for testing)

```bash
# Clone the repository
git clone <your-repo-url>
cd <your-repo-name>

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your Todoist API token
# TODOIST_API_TOKEN=your_actual_token_here

# Run the assistant
python todoist_assistant.py


# Activate the virtual environment
source venv/bin/activate

# Run the main script with todoist source
python main.py --source todoist

# Deactivate the virtual environment (optional, as the script will exit anyway)
deactivate

```

### 5. GitHub Actions Setup (Automated Daily Runs)

1. Fork or clone this repository to your GitHub account

2. Add your Todoist API token as a GitHub secret:
   - Go to your repository on GitHub
   - Click **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `TODOIST_API_TOKEN`
   - Value: paste your Todoist API token
   - Click **Add secret**

3. Enable GitHub Actions:
   - Go to the **Actions** tab in your repository
   - If prompted, enable workflows

4. The assistant will now run automatically every day at 7pm UTC!

### 6. Manual Trigger (Optional)
You can manually trigger the workflow anytime:
- Go to **Actions** tab
- Select "Todoist Assistant" workflow
- Click **Run workflow** → **Run workflow**

## How It Works

1. The assistant fetches all your Todoist tasks
2. It checks each task to see if it's already been processed (looks for 🤖 processed comment)
3. For unprocessed tasks, it applies rules in order:
   - **EnglishWordRule**: If task starts with "english", move to "english-words" project
4. When a task is processed, it adds a comment to mark it as processed

## Project Structure

```
.
├── todoist_assistant.py       # Main application
├── requirements.txt            # Python dependencies
├── .env.example               # Example environment variables
├── .github/
│   └── workflows/
│       └── todoist-assistant.yml  # GitHub Actions workflow
└── README.md                  # This file
```

## Adding New Rules

The code is designed to be easily extensible. To add a new rule:

1. Create a new class that extends `MoveRule`:

```python
class BookRule(MoveRule):
    def __init__(self):
        super().__init__(target_project_name="reading-list")
    
    def matches(self, task_content: str) -> bool:
        return task_content.lower().startswith("book:")
```

2. Add it to the `rules` list in `main()`:

```python
rules: List[TaskRule] = [
    EnglishWordRule(),
    BookRule(),  # Add your new rule here
]
```

## Troubleshooting

### "Project 'english-words' not found"
Make sure you have created a project named exactly `english-words` (lowercase, with hyphen) in your Todoist account.

### GitHub Actions not running
- Check that you've added the `TODOIST_API_TOKEN` secret
- Check the Actions tab for error logs
- Try manually triggering the workflow to test

### Tasks not being processed
- Check that tasks haven't already been processed (look for 🤖 comment)
- Verify the task title starts with "english" (not contains, must start with)
- Check the Actions logs or local run output for error messages

## License

MIT