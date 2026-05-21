import hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import json
from datetime import datetime, date, timedelta, time

from .models import Movie, Show, SeatType, Theatre, Screen, Seat, User, Booking, PrivateBooking

ADMIN_LOGIN_ID = "admin_dbs"
ADMIN_LOGIN_PASSWORD = "DBS_mini"


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def get_seat_pricing_map(show_id, seat_ids=None):
    sql = "SELECT seat_id, final_price FROM seat_pricing WHERE show_id = %s"
    params = [show_id]
    if seat_ids:
        placeholders = ", ".join(["%s"] * len(seat_ids))
        sql += f" AND seat_id IN ({placeholders})"
        params.extend(seat_ids)

    with connection.cursor() as cur:
        cur.execute(sql, params)
        return {int(seat_id): float(final_price) for seat_id, final_price in cur.fetchall()}


# ─── movies ────────────────────────────────────────────────

def get_movies(request):
    movies = Movie.objects.all()
    if g := request.GET.get('genre'):
        movies = movies.filter(genre__icontains=g)
    if y := request.GET.get('year'):
        movies = movies.filter(year=y)
    if t := request.GET.get('title'):
        movies = movies.filter(title__icontains=t)
    return JsonResponse(list(movies.values()), safe=False)


def get_users(request):
    users = User.objects.all().values('user_id', 'name', 'email', 'role')
    return JsonResponse(list(users), safe=False)


# ─── shows ─────────────────────────────────────────────────

def get_shows(request):
    shows = Show.objects.select_related('screen', 'movie')
    if mid := request.GET.get('movie_id'):
        shows = shows.filter(movie_id=mid)
    if d := request.GET.get('date'):
        shows = shows.filter(show_date=d)
    if sid := request.GET.get('screen_id'):
        shows = shows.filter(screen_id=sid)
    if tid := request.GET.get('theatre_id'):
        shows = shows.filter(screen__theatre_id=tid)
    if slot := request.GET.get('slot'):
        slot_map = {
            'MORNING': (time(6, 0), time(11, 59, 59)),
            'AFTERNOON': (time(12, 0), time(16, 59, 59)),
            'EVENING': (time(17, 0), time(20, 59, 59)),
            'NIGHT': (time(21, 0), time(23, 59, 59)),
        }
        if slot.upper() in slot_map:
            slot_start, slot_end = slot_map[slot.upper()]
            shows = shows.filter(start_time__time__gte=slot_start, start_time__time__lte=slot_end)
    return JsonResponse(list(shows.values(
        'show_id', 'movie_id', 'screen_id',
        'movie__title',
        'screen__screen_name',
        'screen__theatre_id',
        'show_date', 'start_time', 'end_time',
        'base_price', 'status'
    )), safe=False)


# ─── theatres & screens ────────────────────────────────────

def get_theatres(request):
    qs = Theatre.objects.all()
    if city := request.GET.get('city'):
        qs = qs.filter(city__icontains=city)
    return JsonResponse(list(qs.values()), safe=False)


def get_screens(request):
    qs = Screen.objects.all()
    if tid := request.GET.get('theatre_id'):
        qs = qs.filter(theatre_id=tid)
    return JsonResponse(list(qs.values()), safe=False)


def get_seat_prices(request):
    return JsonResponse(list(SeatType.objects.all().values()), safe=False)

def _row_label(index):
    # 1 -> A, 2 -> B, ...
    return chr(64 + index)


def ensure_seats_for_screen(screen_id):
    screen = Screen.objects.get(pk=screen_id)
    total_rows = int(screen.total_rows or 0)
    total_cols = int(screen.total_columns or 0)
    if total_rows <= 0 or total_cols <= 0:
        return

    # Build a seat type map for realistic layouts.
    seat_types = {st.name.upper(): int(st.seat_type_id) for st in SeatType.objects.all()}
    normal_id = seat_types.get('NORMAL')
    comfort_id = seat_types.get('COMFORT')
    recliner_id = seat_types.get('RECLINER')
    fallback_id = int(SeatType.objects.order_by('base_price').first().seat_type_id) if SeatType.objects.exists() else 1

    def seat_type_for_row(row_index):
        # Private screens -> Recliner only (cinema-like).
        if (screen.screen_type or '').upper() == 'PRIVATE':
            return recliner_id or fallback_id

        # General rule: premium at the back (higher row index).
        # Last 10% rows -> Recliner, previous 20% -> Comfort, remaining -> Normal.
        recliner_cut = max(1, int(round(total_rows * 0.10)))
        comfort_cut = max(1, int(round(total_rows * 0.20)))
        if row_index > total_rows - recliner_cut:
            return recliner_id or fallback_id
        if row_index > total_rows - (recliner_cut + comfort_cut):
            return comfort_id or fallback_id
        return normal_id or fallback_id

    seats_qs = Seat.objects.filter(screen_id=screen_id)
    if seats_qs.exists():
        # If the screen already has a realistic mix, keep it.
        distinct_types = seats_qs.values('seat_type_id').distinct().count()
        if distinct_types > 1:
            return

        # Rebalance existing seats (fixes older data where all were "Normal").
        recliner_cut = max(1, int(round(total_rows * 0.10)))
        comfort_cut = max(1, int(round(total_rows * 0.20)))
        recliner_start = total_rows - recliner_cut + 1
        comfort_start = total_rows - (recliner_cut + comfort_cut) + 1

        with connection.cursor() as cur:
            if (screen.screen_type or '').upper() == 'PRIVATE':
                cur.execute(
                    "UPDATE SEATS SET seat_type_id = %s WHERE screen_id = %s",
                    [recliner_id or fallback_id, screen_id],
                )
                return

            # Normal rows
            cur.execute(
                "UPDATE SEATS SET seat_type_id = %s WHERE screen_id = %s AND (ASCII(row_label) - 64) < %s",
                [normal_id or fallback_id, screen_id, comfort_start],
            )
            # Comfort rows
            cur.execute(
                "UPDATE SEATS SET seat_type_id = %s WHERE screen_id = %s AND (ASCII(row_label) - 64) >= %s AND (ASCII(row_label) - 64) < %s",
                [comfort_id or fallback_id, screen_id, comfort_start, recliner_start],
            )
            # Recliner rows
            cur.execute(
                "UPDATE SEATS SET seat_type_id = %s WHERE screen_id = %s AND (ASCII(row_label) - 64) >= %s",
                [recliner_id or fallback_id, screen_id, recliner_start],
            )
        return

    # Create seats when missing.
    with connection.cursor() as cur:
        for r in range(1, total_rows + 1):
            row_label = _row_label(r)
            for c in range(1, total_cols + 1):
                cur.execute(
                    "INSERT INTO SEATS (screen_id, row_label, seat_number, seat_type_id) VALUES (%s, %s, %s, %s)",
                    [screen_id, row_label, c, seat_type_for_row(r)],
                )


# ─── seats ─────────────────────────────────────────────────

def get_seats_for_show(request, show_id):
    try:
        show = Show.objects.get(pk=show_id)
    except Show.DoesNotExist:
        return JsonResponse({'error': 'Show not found'}, status=404)

    # Auto-generate seats if missing (helps for newly added screens/shows).
    try:
        ensure_seats_for_screen(show.screen_id)
    except Exception:
        # If seat generation fails, we still attempt to serve existing seats.
        pass

    seats = Seat.objects.filter(screen_id=show.screen_id).select_related('seat_type')

    booked_ids = set(
        Booking.objects.filter(show_id=show_id, status='BOOKED')
        .values_list('seat_id', flat=True)
    )

    pricing = get_seat_pricing_map(show_id)

    data = []
    for seat in seats:
        data.append({
            'seat_id': seat.seat_id,
            'row_label': seat.row_label,
            'seat_number': seat.seat_number,
            'seat_type': seat.seat_type.name,
            'is_booked': seat.seat_id in booked_ids,
            'final_price': pricing.get(seat.seat_id, seat.seat_type.base_price),
        })

    return JsonResponse(data, safe=False)


# ─── auth ──────────────────────────────────────────────────

@csrf_exempt
def register_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    name = body.get('name')
    email = body.get('email')
    password = body.get('password')

    if not all([name, email, password]):
        return JsonResponse({'error': 'name, email, password required'}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Email already registered'}, status=409)

    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO USERS (name, email, password_hash, role) VALUES (%s, %s, %s, 'USER')",
            [name, email, hash_password(password)]
        )

    user = User.objects.get(email=email)
    return JsonResponse({'user_id': user.user_id, 'name': user.name, 'email': user.email}, status=201)


@csrf_exempt
def login_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    email = body.get('email')
    password = body.get('password')

    try:
        user = User.objects.get(email=email, password_hash=hash_password(password))
        return JsonResponse({'user_id': user.user_id, 'name': user.name, 'role': user.role})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Invalid credentials'}, status=401)


def parse_iso_datetime(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def has_admin_access(admin_email, admin_password):
    return admin_email == ADMIN_LOGIN_ID and admin_password == ADMIN_LOGIN_PASSWORD


def check_screen_overlap(screen_id, start_time, end_time, show_date):
    show_conflict = Show.objects.filter(
        screen_id=screen_id,
        show_date=show_date,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exists()
    private_conflict = PrivateBooking.objects.filter(
        screen_id=screen_id,
        booking_date=show_date,
        status='CONFIRMED',
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exists()
    return show_conflict or private_conflict


@csrf_exempt
def admin_create_show(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    admin_email = body.get('admin_email')
    admin_password = body.get('admin_password')
    movie_id = body.get('movie_id')
    screen_id = body.get('screen_id')
    show_date = body.get('show_date')
    start_time = body.get('start_time')
    end_time = body.get('end_time')
    base_price = body.get('base_price')
    status = body.get('status', 'SCHEDULED')

    if not all([admin_email, admin_password, movie_id, screen_id, show_date, start_time, end_time]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    if not has_admin_access(admin_email, admin_password):
        return JsonResponse({'error': 'Invalid admin credentials'}, status=401)

    try:
        parsed_show_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        parsed_start_time = parse_iso_datetime(start_time)
        parsed_end_time = parse_iso_datetime(end_time)
    except ValueError:
        return JsonResponse({'error': 'Invalid date/time format'}, status=400)

    if parsed_end_time <= parsed_start_time:
        parsed_end_time = parsed_end_time + timedelta(days=1)

    if not Movie.objects.filter(pk=movie_id).exists():
        return JsonResponse({'error': 'Movie not found'}, status=404)
    if not Screen.objects.filter(pk=screen_id).exists():
        return JsonResponse({'error': 'Screen not found'}, status=404)
    if check_screen_overlap(screen_id, parsed_start_time, parsed_end_time, parsed_show_date):
        return JsonResponse({'error': 'Screen already has another booking/show in this slot'}, status=409)

    # If base_price is not provided, derive from the lowest seat type base price.
    if base_price in [None, '']:
        default_seat_type = SeatType.objects.order_by('base_price').first()
        base_price = float(default_seat_type.base_price) if default_seat_type else 0

    show = Show.objects.create(
        movie_id=movie_id,
        screen_id=screen_id,
        show_date=parsed_show_date,
        start_time=parsed_start_time,
        end_time=parsed_end_time,
        base_price=base_price,
        status=status,
    )

    return JsonResponse({
        'message': 'Show created successfully',
        'show_id': show.show_id,
        'created_by': ADMIN_LOGIN_ID,
    }, status=201)


@csrf_exempt
def admin_add_movie(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    admin_email = body.get('admin_email')
    admin_password = body.get('admin_password')
    movie_id = body.get('movie_id')
    title = body.get('title')
    year = body.get('year')
    genre = body.get('genre')
    overview = body.get('overview')
    director = body.get('director')
    cast_members = body.get('cast_members')

    if not all([admin_email, admin_password, movie_id, title]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    if not has_admin_access(admin_email, admin_password):
        return JsonResponse({'error': 'Invalid admin credentials'}, status=401)

    if Movie.objects.filter(pk=movie_id).exists():
        return JsonResponse({'error': 'Movie ID already exists'}, status=409)

    Movie.objects.create(
        movie_id=movie_id,
        title=title,
        year=year,
        genre=genre,
        overview=overview,
        director=director,
        cast_members=cast_members,
    )
    return JsonResponse({'message': 'Movie added successfully', 'movie_id': movie_id}, status=201)


@csrf_exempt
def admin_add_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    admin_email = body.get('admin_email')
    admin_password = body.get('admin_password')
    name = body.get('name')
    email = body.get('email')
    password = body.get('password')
    role = body.get('role', 'USER')

    if not has_admin_access(admin_email, admin_password):
        return JsonResponse({'error': 'Invalid admin credentials'}, status=401)

    if not all([name, email, password]):
        return JsonResponse({'error': 'name, email, password required'}, status=400)

    if role not in ['ADMIN', 'USER']:
        return JsonResponse({'error': 'role must be ADMIN or USER'}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Email already registered'}, status=409)

    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO USERS (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            [name, email, hash_password(password), role]
        )

    created = User.objects.get(email=email)
    return JsonResponse({'message': 'User created', 'user_id': created.user_id}, status=201)


@csrf_exempt
def admin_create_private_show(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    admin_email = body.get('admin_email')
    admin_password = body.get('admin_password')
    movie_id = body.get('movie_id')
    screen_id = body.get('screen_id')
    show_date = body.get('show_date')
    start_time = body.get('start_time')
    end_time = body.get('end_time')
    flat_fee = body.get('flat_fee', 5000)

    if not all([admin_email, admin_password, movie_id, screen_id, show_date, start_time, end_time]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    if not has_admin_access(admin_email, admin_password):
        return JsonResponse({'error': 'Invalid admin credentials'}, status=401)

    try:
        parsed_show_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        parsed_start_time = parse_iso_datetime(start_time)
        parsed_end_time = parse_iso_datetime(end_time)
    except ValueError:
        return JsonResponse({'error': 'Invalid date/time format'}, status=400)

    if parsed_show_date < (date.today() + timedelta(days=1)):
        return JsonResponse({'error': 'Private shows can be scheduled from tomorrow onward'}, status=400)

    if parsed_end_time <= parsed_start_time:
        parsed_end_time = parsed_end_time + timedelta(days=1)

    try:
        screen = Screen.objects.get(pk=screen_id)
    except Screen.DoesNotExist:
        return JsonResponse({'error': 'Screen not found'}, status=404)

    if screen.screen_type != 'PRIVATE':
        return JsonResponse({'error': 'Selected screen is not a private screen'}, status=400)

    if not Movie.objects.filter(pk=movie_id).exists():
        return JsonResponse({'error': 'Movie not found'}, status=404)

    if check_screen_overlap(screen_id, parsed_start_time, parsed_end_time, parsed_show_date):
        return JsonResponse({'error': 'Private screen already booked for this slot'}, status=409)

    with connection.cursor() as cur:
        cur.execute(
            """INSERT INTO PRIVATE_BOOKINGS
               (user_id, screen_id, movie_id, booking_date, start_time, end_time, flat_fee, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'CONFIRMED')""",
            [1, screen_id, movie_id, parsed_show_date, parsed_start_time, parsed_end_time, flat_fee]
        )
    pb = PrivateBooking.objects.filter(
        screen_id=screen_id,
        movie_id=movie_id,
        booking_date=parsed_show_date,
        status='CONFIRMED'
    ).order_by('-private_booking_id').first()
    return JsonResponse({
        'message': 'Private show added (booked by ADMIN)',
        'booked_by': 'ADMIN',
        'private_booking_id': pb.private_booking_id,
        'screen_id': screen.screen_id,
        'screen_name': screen.screen_name,
    }, status=201)


# ─── bookings ──────────────────────────────────────────────

@csrf_exempt
def create_booking(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    show_id = body.get('show_id')
    seat_ids = body.get('seat_ids', [])
    user_id = body.get('user_id')

    if not all([show_id, seat_ids, user_id]):
        return JsonResponse({'error': 'show_id, seat_ids, user_id required'}, status=400)

    already_booked = list(
        Booking.objects.filter(
            show_id=show_id, seat_id__in=seat_ids, status='BOOKED'
        ).values_list('seat_id', flat=True)
    )
    if already_booked:
        return JsonResponse({'error': f'Seats already booked: {already_booked}'}, status=409)

    pricing = get_seat_pricing_map(show_id, seat_ids)

    created = []
    with connection.cursor() as cur:
        for seat_id in seat_ids:
            price = pricing.get(seat_id, 0)
            cur.execute(
                """INSERT INTO BOOKINGS (show_id, seat_id, user_id, total_price, status)
                   VALUES (%s, %s, %s, %s, 'BOOKED')""",
                [show_id, seat_id, user_id, price]
            )
            created.append({'seat_id': seat_id, 'price': price})

    return JsonResponse({
        'booked': created,
        'total': sum(c['price'] for c in created)
    }, status=201)


def get_user_bookings(request, user_id):
    bookings = Booking.objects.filter(user_id=user_id).select_related('show', 'seat', 'seat__seat_type')
    data = []
    for b in bookings:
        data.append({
            'booking_id': b.booking_id,
            'show_id': b.show_id,
            'movie_id': b.show.movie_id,
            'show_date': b.show.show_date,
            'start_time': b.show.start_time,
            'seat_id': b.seat_id,
            'row_label': b.seat.row_label,
            'seat_number': b.seat.seat_number,
            'seat_type': b.seat.seat_type.name,
            'total_price': b.total_price,
            'status': b.status,
            'booked_at': b.booked_at,
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
def cancel_booking(request, booking_id):
    if request.method != 'PATCH':
        return JsonResponse({'error': 'PATCH only'}, status=405)
    try:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE BOOKINGS SET status = 'CANCELLED' WHERE booking_id = %s",
                [booking_id]
            )
        return JsonResponse({'message': 'Booking cancelled'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── private bookings ──────────────────────────────────────

@csrf_exempt
def create_private_booking(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    body = json.loads(request.body)
    user_id      = body.get('user_id')
    movie_id     = body.get('movie_id')
    screen_id    = body.get('screen_id')
    booking_date = body.get('booking_date')
    start_time   = body.get('start_time')
    end_time     = body.get('end_time')

    if not all([user_id, movie_id, booking_date, start_time, end_time]):
        return JsonResponse(
            {'error': 'user_id, movie_id, booking_date, start_time, end_time are required'},
            status=400
        )

    if not User.objects.filter(pk=user_id).exists():
        return JsonResponse({'error': 'User not found'}, status=404)

    if not Movie.objects.filter(pk=movie_id).exists():
        return JsonResponse({'error': 'Movie not found'}, status=404)

    try:
        parsed_booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        parsed_start_time = parse_iso_datetime(start_time)
        parsed_end_time = parse_iso_datetime(end_time)
    except ValueError:
        return JsonResponse({'error': 'Invalid date/time format'}, status=400)

    if parsed_end_time <= parsed_start_time:
        parsed_end_time = parsed_end_time + timedelta(days=1)

    if screen_id:
        try:
            chosen_screen = Screen.objects.get(pk=screen_id)
        except Screen.DoesNotExist:
            return JsonResponse({'error': 'Selected screen not found'}, status=404)
        if chosen_screen.screen_type != 'PRIVATE':
            return JsonResponse({'error': 'Selected screen is not private'}, status=400)
        private_screens = Screen.objects.filter(screen_id=chosen_screen.screen_id)
    else:
        private_screens = Screen.objects.filter(screen_type='PRIVATE')
        if not private_screens.exists():
            return JsonResponse({'error': 'No private screens available'}, status=404)

    available_screen = None
    for screen in private_screens:
        conflict = PrivateBooking.objects.filter(
            screen_id=screen.screen_id,
            status='CONFIRMED',
            start_time__lt=parsed_end_time,
            end_time__gt=parsed_start_time
        )
        if not conflict.exists():
            available_screen = screen
            break

    if not available_screen:
        return JsonResponse(
            {'error': 'No private screens available for this date and time'},
            status=409
        )

    with connection.cursor() as cur:
        cur.execute(
            """INSERT INTO PRIVATE_BOOKINGS
               (user_id, screen_id, movie_id, booking_date, start_time, end_time, flat_fee, status)
               VALUES (%s, %s, %s, %s, %s, %s, 5000, 'CONFIRMED')""",
            [user_id, available_screen.screen_id, movie_id, parsed_booking_date, parsed_start_time, parsed_end_time]
        )

    pb = PrivateBooking.objects.filter(
        user_id=user_id,
        screen_id=available_screen.screen_id,
        booking_date=parsed_booking_date,
        status='CONFIRMED'
    ).order_by('-private_booking_id').first()

    return JsonResponse({
        'private_booking_id': pb.private_booking_id,
        'screen_id': pb.screen.screen_id,
        'screen_name': pb.screen.screen_name,
        'movie_id': pb.movie_id,
        'booking_date': pb.booking_date,
        'start_time': pb.start_time,
        'end_time': pb.end_time,
        'flat_fee': pb.flat_fee,
        'status': pb.status,
    }, status=201)


def get_private_bookings(request, user_id):
    bookings = PrivateBooking.objects.filter(user_id=user_id).select_related('screen', 'movie')
    data = []
    for pb in bookings:
        data.append({
            'private_booking_id': pb.private_booking_id,
            'movie_id': pb.movie_id,
            'movie_title': pb.movie.title,
            'screen_name': pb.screen.screen_name,
            'booking_date': pb.booking_date,
            'start_time': pb.start_time,
            'end_time': pb.end_time,
            'flat_fee': pb.flat_fee,
            'status': pb.status,
            'booked_at': pb.booked_at,
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
def cancel_private_booking(request, pb_id):
    if request.method != 'PATCH':
        return JsonResponse({'error': 'PATCH only'}, status=405)
    try:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE PRIVATE_BOOKINGS SET status = 'CANCELLED' WHERE private_booking_id = %s",
                [pb_id]
            )
        return JsonResponse({'message': 'Private booking cancelled'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)