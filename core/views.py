from django.shortcuts import render
from .models import Search
from .forms import SearchForm

# Create your views here.
def searchView(request):
    form = SearchForm()
    return render(request, 'core/home.html', {'form': form})


def searchResults(request):
    return render(request, 'core/search_results.html')