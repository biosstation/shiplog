from django.shortcuts import render

def index(request):
	return render(request, 'index.html')

def event(request):
	context = {}
	system = request.POST.get('system', None)
	context['system'] = system
	return render(request, 'event.html', context)
