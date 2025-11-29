from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Task
from .forms import TaskForm
from django.contrib import messages

@login_required(login_url="accounts:login")
def task_list(request):
    """List all tasks for admin."""
    tasks = Task.objects.all().order_by('-created_at')
    return render(request, "tasks/task_list.html", {"tasks": tasks})

@login_required(login_url="accounts:login")
def task_create(request):
    """Create a new task."""
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Task created successfully!")
            return redirect("tasks:task_list")
    else:
        form = TaskForm()
    return render(request, "tasks/task_form.html", {"form": form})

@login_required(login_url="accounts:login")
def task_update(request, pk):
    """Update existing task."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully!")
            return redirect("tasks:task_list")
    else:
        form = TaskForm(instance=task)
    return render(request, "tasks/task_form.html", {"form": form})

@login_required(login_url="accounts:login")
def task_delete(request, pk):
    """Delete a task."""
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted successfully!")
        return redirect("tasks:task_list")
    return render(request, "tasks/task_confirm_delete.html", {"task": task})
