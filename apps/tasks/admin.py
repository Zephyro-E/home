from django.contrib import admin

from .models import Subtask, Task, TaskComment, TaskLabel


class SubtaskInline(admin.TabularInline):
    model = Subtask
    extra = 0


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "assignee", "due_date", "visibility", "household"]
    list_filter = ["status", "visibility", "household"]
    inlines = [SubtaskInline, TaskCommentInline]


@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ["name", "color", "household"]
