from django.db import models
import uuid

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    github_url = models.URLField(max_length=500, null=True, blank=True)
    local_path = models.CharField(max_length=1000, null=True, blank=True)
    workspace_id = models.CharField(max_length=255, null=True, blank=True)
    tech_stack = models.JSONField(default=list)
    team_members = models.JSONField(default=list)
    blueprint = models.JSONField(default=dict)
    status = models.CharField(max_length=50, default="active")
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Feature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='features', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.CharField(max_length=255, default="Developer")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="backlog")
    spec = models.JSONField(default=dict)
    suggestions = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.title

class FeatureHistory(models.Model):
    feature = models.ForeignKey(Feature, related_name="pipeline_history", on_delete=models.CASCADE)
    stage = models.CharField(max_length=50)
    action = models.CharField(max_length=50)
    by = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

class FeatureApproval(models.Model):
    feature = models.ForeignKey(Feature, related_name="approvals", on_delete=models.CASCADE)
    by = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    comment = models.TextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

class TestResult(models.Model):
    feature = models.OneToOneField(Feature, related_name="test_results", on_delete=models.CASCADE)
    overall_status = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    summary = models.TextField()
    tests = models.JSONField(default=list)
    coverage = models.IntegerField(default=0)
    suggestions = models.JSONField(default=list)
    blockers = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

class Comment(models.Model):
    feature = models.ForeignKey(Feature, related_name="comments", on_delete=models.CASCADE)
    text = models.TextField()
    author = models.CharField(max_length=255, default="Developer")
    at = models.DateTimeField(auto_now_add=True)

class Changeset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='changesets', on_delete=models.CASCADE)
    feature = models.ForeignKey(Feature, related_name='changesets', on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending")
    ai_review = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class FileDiff(models.Model):
    changeset = models.ForeignKey(Changeset, related_name='files_changed', on_delete=models.CASCADE)
    file_path = models.CharField(max_length=1000)
    diff_content = models.TextField()
    action = models.CharField(max_length=50, choices=[("added", "Added"), ("modified", "Modified"), ("deleted", "Deleted")])

class AgentRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='agent_runs', on_delete=models.CASCADE)
    agent_type = models.CharField(max_length=100)
    status = models.CharField(max_length=50, default="running")
    logs = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class ChatMessage(models.Model):
    project = models.ForeignKey(Project, related_name='chat_messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=50) # user or assistant
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class WorkingMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='working_memories', on_delete=models.CASCADE)
    scope = models.CharField(max_length=100, default='implementation')
    summary = models.TextField()
    context = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('project', 'scope')


class EpisodicMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='episodic_memories', on_delete=models.CASCADE)
    memory_type = models.CharField(max_length=100, default='implementation')
    title = models.CharField(max_length=255)
    summary = models.TextField()
    related_files = models.JSONField(default=list)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class SemanticMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='semantic_memories', on_delete=models.CASCADE)
    file_path = models.CharField(max_length=1000)
    chunk_index = models.PositiveIntegerField(default=0)
    symbol = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    keywords = models.JSONField(default=list)
    metadata = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('project', 'file_path', 'chunk_index')
