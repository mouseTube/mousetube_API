class OrcidProcessSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/accounts/orcid/login/"):
            process = request.GET.get("process")
            if process:
                request.session["orcid_process"] = process
        response = self.get_response(request)
        return response
