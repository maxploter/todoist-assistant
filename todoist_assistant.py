"""
Todoist Assistant - Automates task organization
Story 1: Move tasks starting with "english" to "english-words" project
"""

import os
import logging
import sys
from datetime import datetime, timedelta, timezone
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
DRY_RUN = "--dry-run" in sys.argv


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
    """Fetch all active inbox tasks"""
    try:
      tasks_iterator = self.api.filter_tasks(query="#inbox")
      all_tasks = []
      for task_list in tasks_iterator:
        all_tasks.extend(task_list)
      return all_tasks
    except Exception as e:
      logger.error(f"Failed to fetch tasks: {e}")
      return []

  def get_section_id(self, project_id: str, section_name: str) -> Optional[str]:
    """Look up section_id by name in project_id (case-insensitive). Never creates sections."""
    if not hasattr(self, '_sections_cache'):
      self._sections_cache = {}
    cache_key = (project_id, section_name.lower())
    if cache_key not in self._sections_cache:
      try:
        sections = []
        for sl in self.api.get_sections(project_id=project_id):
          sections.extend(sl)
        for s in sections:
          self._sections_cache[(project_id, s.name.lower())] = s.id
      except Exception as e:
        logger.error(f"Failed to fetch sections for project {project_id}: {e}")
        return None
      if cache_key not in self._sections_cache:
        logger.warning(f"Section '{section_name}' not found in project {project_id}. Moving to project root.")
        return None
    return self._sections_cache[cache_key]

  def get_task_comments(self, task_id: str) -> List:
    """Fetch comments for a task"""
    try:
      return self.api.get_comments(task_id=task_id)
    except Exception as e:
      logger.error(f"Failed to fetch comments for task {task_id}: {e}")
      return []

  def move_task(self, task_id: str, project_id: str, section_id: Optional[str] = None) -> bool:
    """Move task to a different project (and optional section)"""
    if DRY_RUN:
      return True
    try:
      self.api.move_task(task_id=task_id, project_id=project_id, section_id=section_id)
      return True
    except Exception as e:
      logger.error(f"Failed to move task {task_id}: {e}")
      return False

  def add_comment(self, task_id: str, message: str):
    """Add a comment to a task"""
    if DRY_RUN:
      return
    try:
      comment = f"{BOT_SIGNATURE}: {message}"
      self.api.add_comment(task_id=task_id, content=comment)
    except Exception as e:
      logger.error(f"Failed to add comment to task {task_id}: {e}")


class TaskRule(ABC):
  """Abstract base class for task processing rules"""

  @abstractmethod
  def matches(self, task) -> bool:
    """Check if this rule applies to the task"""
    pass

  @abstractmethod
  def execute(self, task, service: TodoistService) -> bool:
    """Execute the rule. Returns True if successful"""
    pass


class MoveRule(TaskRule):
  """Base class for rules that move tasks to a specific project (and optional section)"""

  def __init__(self, target_project_name: str, target_section_name: Optional[str] = None):
    self.target_project_name = target_project_name
    self.target_section_name = target_section_name

  def _section_name_for(self, task_content: str) -> Optional[str]:
    """Return the section name for this task. Override in subclasses for per-task routing."""
    return self.target_section_name

  def execute(self, task, service: TodoistService) -> bool:
    """Move the task to the target project (and section if specified)"""
    project_id = service.get_project_id(self.target_project_name)

    if not project_id:
      logger.warning(f"Project '{self.target_project_name}' not found. Skipping move.")
      return False

    section_id = None
    section_name = self._section_name_for(task.content)
    if section_name:
      section_id = service.get_section_id(project_id, section_name)
      # get_section_id logs a warning if not found; we proceed to project root

    # Move the task
    if not service.move_task(task.id, project_id, section_id=section_id):
      return False

    # Add comment
    rule_name = self.__class__.__name__
    dest = f"'{self.target_project_name}'"
    if section_name:
      dest += f" / {section_name}"
    message = f"Moved to {dest} by {rule_name}"
    service.add_comment(task.id, message)

    logger.info(f"✓ {rule_name}: Moved '{task.content}' → {dest}")
    return True



class PrefixMoveRule(MoveRule):
  """Config-driven rule: move tasks whose content starts with any of the given prefixes"""

  def __init__(self, prefix: str, target_project_name: str,
               target_section_name: Optional[str] = None):
    super().__init__(target_project_name=target_project_name,
                     target_section_name=target_section_name)
    self.prefix = prefix.lower()

  def matches(self, task) -> bool:
    return task.content.lower().startswith(self.prefix)


class StaleMoveRule(MoveRule):
  """Move inbox tasks older than max_age_days, unless they have a due date or a label"""

  def __init__(self, max_age_days: int, target_project_name: str):
    super().__init__(target_project_name=target_project_name)
    self.max_age = timedelta(days=max_age_days)

  def matches(self, task) -> bool:
    if task.due or task.labels:
      return False
    created_at = task.created_at
    if created_at.tzinfo is None:
      created_at = created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created_at > self.max_age



def is_task_already_processed(task, service: TodoistService) -> bool:
  """Check if task has already been processed by the bot"""
  if True or task.comment_count == 0: # Disable this check for now
    return False

  comments = service.get_task_comments(task.id)
  return any(BOT_SIGNATURE in comment.content for comment in comments)


def main():
  """Main execution loop"""
  logger.info("Starting Todoist Assistant..." + (" (dry run: nothing is moved)" if DRY_RUN else ""))

  # Initialize service
  try:
    service = TodoistService()
  except ValueError as e:
    logger.critical(f"Failed to initialize: {e}")
    sys.exit(1)

  # Define active rules (first match wins)
  rules: List[TaskRule] = [
    PrefixMoveRule("english",  "english-words"),
    PrefixMoveRule("feedback", "Feedback/retro"),
    PrefixMoveRule("idea",     "Ideas"),
    PrefixMoveRule("book",     "Fun/entertainment", target_section_name="Books"),
    PrefixMoveRule("movie",    "Fun/entertainment", target_section_name="Movies"),
    PrefixMoveRule("game",     "Fun/entertainment", target_section_name="Games"),
    PrefixMoveRule("hobby",    "Fun/entertainment", target_section_name="Hobby"),
    StaleMoveRule(30, "Inbox Stale"),  # keep last: only tasks no other rule took
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
      if rule.matches(task):
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
