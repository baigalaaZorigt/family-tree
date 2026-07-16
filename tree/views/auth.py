from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .permissions import current_person


def login_view(request):
    # Гэр бүлийн хүнээр аль хэдийн нэвтэрсэн бол нүүр рүү.
    # (admin superuser — Person холбоосгүй — нэвтрэх боломжтой хэвээр үлдэнэ)
    if request.method == 'GET' and current_person(request) is not None:
        return redirect('/')
    error = None
    if request.method == 'POST':
        phone = request.POST.get('username', '').strip()
        birth = request.POST.get('password', '').strip()
        user = authenticate(request, username=phone, password=birth)
        if user is not None:
            login(request, user)
            return redirect('/')
        error = 'Утас эсвэл төрсөн огноо буруу байна. (Нууц үг = төрсөн огноо, ж: 1965.02.26)'
    return render(request, 'tree/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('/')
