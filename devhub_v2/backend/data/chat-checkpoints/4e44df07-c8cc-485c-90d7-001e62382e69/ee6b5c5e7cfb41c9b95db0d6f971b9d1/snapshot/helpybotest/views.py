from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def api_create_flow(request):
    # ...existing code...
    pass

@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def api_get_flow(request, flow_id):
    # ...existing code...
    pass

@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def api_update_flow(request, flow_id):
    # ...existing code...
    pass

# Add @csrf_exempt to other API views as needed
