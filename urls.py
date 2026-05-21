from django.urls import path
from .views import (
    get_movies, get_users, get_shows, get_seat_prices,
    get_theatres, get_screens,
    get_seats_for_show,
    register_user, login_user,
    admin_create_show,
    admin_add_movie, admin_add_user, admin_create_private_show,
    create_booking, get_user_bookings, cancel_booking,
    create_private_booking,
    get_private_bookings,
    cancel_private_booking,
)

urlpatterns = [
    path('movies/', get_movies),
    path('users/', get_users),
    path('shows/', get_shows),
    path('seat-prices/', get_seat_prices),

    path('theatres/', get_theatres),
    path('screens/', get_screens),

    path('seats/<int:show_id>/', get_seats_for_show),   # seat layout + availability + price

    path('register/', register_user),
    path('login/', login_user),
    path('admin/shows/', admin_create_show),
    path('admin/movies/', admin_add_movie),
    path('admin/users/', admin_add_user),
    path('admin/private-shows/', admin_create_private_show),

    path('bookings/', create_booking),                        # POST
    path('bookings/user/<int:user_id>/', get_user_bookings),  # GET
    path('bookings/<int:booking_id>/cancel/', cancel_booking), # PATCH

    path('private-bookings/', create_private_booking),                          # POST
    path('private-bookings/user/<int:user_id>/', get_private_bookings),         # GET
    path('private-bookings/<int:pb_id>/cancel/', cancel_private_booking),
]