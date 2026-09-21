"""Shared Streamlit session-state keys.

Keeping the key names in one place reduces accidental divergence between pages.
"""

from __future__ import annotations


CONTAINER = "container"
PROJECT_SAVE_PATH = "project_save_path"
PROJECT_SAVE_MESSAGE = "_project_save_message"
PROJECT_UPLOAD_DIGEST = "_project_upload_digest"
PLOT_SAVE_PATH = "plot_save_path"
PLOT_SAVE_MESSAGE = "_plot_save_message"
DETAIL_SAVE_PATH = "detail_save_path"
DETAIL_SAVE_MESSAGE = "_detail_save_message"
ACTIVE_GROUP_ID = "_active_group_id"
ACTIVE_PARAMETER_SECTION = "_active_parameter_section"
GROUP_ADDED = "_group_added"
NEW_GROUP_NAME = "new_group_name"
NEW_GROUP_NAME_AUTO = "_new_group_name_auto"
