"""
Todoist Assistant - Automates task organization
Story 1: Move tasks starting with "english" to "english-words" project
"""

import os
import logging
import sys
from abc import ABC, abstractmethod
from typing import List, Optional

from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI

# Setup Logging
logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - [%(levelname)s] - %(message)s',
  handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()

# Constants
BOT_SIGNATURE = "🤖 processed"


class TodoistService:
  """Wrapper for Todoist API operations"""

  def __init__(self):
    token = os.getenv("TODOIST_API_TOKEN")
    if not token:
      raise ValueError("Missing TODOIST_API_TOKEN in environment variables")

    self.api = TodoistAPI(token)
    self.projects_cache = None

  def get_projects(self):
    """Fetch and cache projects"""
    if self.projects_cache is None:
      try:
        projects = []
        projects_iterator = self.api.get_projects()
        for projects_list in projects_iterator:
          projects.extend(projects_list)
        self.projects_cache = {p.name.lower(): p.id for p in projects}
        logger.info(f"Loaded {len(self.projects_cache)} projects")
      except Exception as e:
        logger.error(f"Failed to fetch projects: {e}")
        self.projects_cache = {}
    return self.projects_cache

  def get_project_id(self, project_name: str) -> Optional[str]:
    """Get project ID by name (case-insensitive)"""
    projects = self.get_projects()
    return projects.get(project_name.lower())

  def get_tasks(self) -> List:
    """Fetch all active tasks"""
    try:
      tasks_iterator = self.api.filter_tasks(
        query="#inbox & search: english"
      )
      all_tasks = []
      for task_list in tasks_iterator:
        all_tasks.extend(task_list)
      return all_tasks


    except Exception as e:
      logger.error(f"Failed to fetch tasks: {e}")
      return []

  def get_task_comments(self, task_id: str) -> List:
    """Fetch comments for a task"""
    try:
      return self.api.get_comments(task_id=task_id)
    except Exception as e:
      logger.error(f"Failed to fetch comments for task {task_id}: {e}")
      return []

  def move_task(self, task_id: str, project_id: str) -> bool:
    """Move task to a different project"""
    try:
      self.api.move_task(task_id=task_id, project_id=project_id)
      return True
    except Exception as e:
      logger.error(f"Failed to move task {task_id}: {e}")
      return False

  def add_comment(self, task_id: str, message: str):
    """Add a comment to a task"""
    try:
      comment = f"{BOT_SIGNATURE}: {message}"
      self.api.add_comment(task_id=task_id, content=comment)
    except Exception as e:
      logger.error(f"Failed to add comment to task {task_id}: {e}")


class TaskRule(ABC):
  """Abstract base class for task processing rules"""

  @abstractmethod
  def matches(self, task_content: str) -> bool:
    """Check if this rule applies to the task"""
    pass

  @abstractmethod
  def execute(self, task, service: TodoistService) -> bool:
    """Execute the rule. Returns True if successful"""
    pass


class MoveRule(TaskRule):
  """Base class for rules that move tasks to a specific project"""

  def __init__(self, target_project_name: str):
    self.target_project_name = target_project_name

  def execute(self, task, service: TodoistService) -> bool:
    """Move the task to the target project"""
    project_id = service.get_project_id(self.target_project_name)

    if not project_id:
      logger.warning(f"Project '{self.target_project_name}' not found. Skipping move.")
      return False

    # Move the task
    if not service.move_task(task.id, project_id):
      return False

    # Add comment
    rule_name = self.__class__.__name__
    message = f"Moved to '{self.target_project_name}' by {rule_name}"
    service.add_comment(task.id, message)

    logger.info(f"✓ {rule_name}: Moved '{task.content}' → {self.target_project_name}")
    return True


class EnglishWordRule(MoveRule):
  """Move tasks starting with 'english' to 'english-words' project"""

  def __init__(self):
    super().__init__(target_project_name="english-words")

  def matches(self, task_content: str) -> bool:
    """Check if task starts with 'english' (case-insensitive)"""
    return task_content.lower().startswith("english")


def is_task_already_processed(task, service: TodoistService) -> bool:
  """Check if task has already been processed by the bot"""
  if True or task.comment_count == 0: # Disable this check for now
    return False

  comments = service.get_task_comments(task.id)
  return any(BOT_SIGNATURE in comment.content for comment in comments)


def main():
  """Main execution loop"""
  logger.info("Starting Todoist Assistant...")

  # Initialize service
  try:
    service = TodoistService()
  except ValueError as e:
    logger.critical(f"Failed to initialize: {e}")
    sys.exit(1)

  # Define active rules
  rules: List[TaskRule] = [
    EnglishWordRule(),
  ]

  # Fetch tasks
  tasks = service.get_tasks()
  logger.info(f"Found {len(tasks)} tasks")

  processed_count = 0
  skipped_count = 0

  for task in tasks:
    # Skip already processed tasks
    if is_task_already_processed(task, service):
      logger.debug(f"Skipping already processed task: {task.content}")
      skipped_count += 1
      continue

    # Try to match against rules
    rule_matched = False
    for rule in rules:
      if rule.matches(task.content):
        logger.info(f"Processing: {task.content}")
        success = rule.execute(task, service)
        if success:
          rule_matched = True
          processed_count += 1
          break  # Stop after first matching rule

    if not rule_matched:
      logger.debug(f"No rule matched for: {task.content}")

  logger.info(f"Finished! Processed: {processed_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
  main()
