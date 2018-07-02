from django.shortcuts import render

def index(request):
	return render(request, 'index.html')

def event(request):
	return render(request, 'event.html')
