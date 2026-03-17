from django.contrib import admin
from .models import Project, Feature, FeatureHistory, FeatureApproval, TestResult, Comment, Changeset, FileDiff, AgentRun, ChatMessage

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'registered_at')
    search_fields = ('name', 'description')

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'project')
    search_fields = ('title',)

@admin.register(Changeset)
class ChangesetAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'created_at')
    list_filter = ('status', 'project')

admin.site.register(FeatureHistory)
admin.site.register(FeatureApproval)
admin.site.register(TestResult)
admin.site.register(Comment)
admin.site.register(FileDiff)
admin.site.register(AgentRun)
admin.site.register(ChatMessage)
