from django.db import models


class Movie(models.Model):
    movie_id = models.CharField(primary_key=True, max_length=20)
    title = models.CharField(max_length=200)
    year = models.IntegerField(null=True)
    genre = models.CharField(max_length=200, null=True)
    overview = models.TextField(null=True)
    director = models.CharField(max_length=100, null=True)
    cast_members = models.CharField(max_length=500, null=True, db_column='cast_members')

    class Meta:
        db_table = "MOVIES"
        managed = False


class Theatre(models.Model):
    theatre_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=50, null=True)
    address = models.CharField(max_length=200, null=True)

    class Meta:
        db_table = 'THEATRES'
        managed = False


class Screen(models.Model):
    screen_id = models.AutoField(primary_key=True)
    theatre = models.ForeignKey(Theatre, on_delete=models.DO_NOTHING, db_column='theatre_id')
    screen_name = models.CharField(max_length=50, null=True)
    total_rows = models.IntegerField(null=True)
    total_columns = models.IntegerField(null=True)
    screen_type = models.CharField(max_length=20, null=True)

    class Meta:
        db_table = 'SCREENS'
        managed = False


class SeatType(models.Model):
    seat_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=30)
    base_price = models.FloatField()

    class Meta:
        db_table = 'SEAT_TYPES'
        managed = False


class Seat(models.Model):
    seat_id = models.AutoField(primary_key=True)
    screen = models.ForeignKey(Screen, on_delete=models.DO_NOTHING, db_column='screen_id')
    row_label = models.CharField(max_length=5, null=True)
    seat_number = models.IntegerField(null=True)
    seat_type = models.ForeignKey(SeatType, on_delete=models.DO_NOTHING, db_column='seat_type_id')

    class Meta:
        db_table = 'SEATS'
        managed = False


class Show(models.Model):
    show_id = models.AutoField(primary_key=True)
    movie = models.ForeignKey(Movie, on_delete=models.DO_NOTHING, db_column='movie_id')
    screen = models.ForeignKey(Screen, on_delete=models.DO_NOTHING, db_column='screen_id')
    show_date = models.DateField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20)

    class Meta:
        db_table = 'SHOWS'
        managed = False


class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, null=True)
    email = models.CharField(max_length=100, unique=True, null=True)
    password_hash = models.CharField(max_length=200, null=True)
    role = models.CharField(max_length=20, default='USER')

    class Meta:
        db_table = 'USERS'
        managed = False


class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    show = models.ForeignKey(Show, on_delete=models.DO_NOTHING, db_column='show_id')
    seat = models.ForeignKey(Seat, on_delete=models.DO_NOTHING, db_column='seat_id')
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='user_id')
    total_price = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    status = models.CharField(max_length=20, default='BOOKED')
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'BOOKINGS'
        managed = False
        unique_together = [('show', 'seat')]


class SeatPricing(models.Model):
    show = models.ForeignKey(Show, on_delete=models.DO_NOTHING, db_column='show_id')
    seat_id = models.IntegerField()
    base_price = models.FloatField()
    demand_multiplier = models.FloatField()
    final_price = models.FloatField()

    class Meta:
        db_table = "SEAT_PRICING"
        managed = False



class PrivateBooking(models.Model):
    private_booking_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='user_id')
    screen = models.ForeignKey(Screen, on_delete=models.DO_NOTHING, db_column='screen_id')
    movie = models.ForeignKey(Movie, on_delete=models.DO_NOTHING, db_column='movie_id')
    booking_date = models.DateField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    flat_fee = models.DecimalField(max_digits=8, decimal_places=2, default=5000)
    status = models.CharField(max_length=20, default='CONFIRMED')
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'PRIVATE_BOOKINGS'
        managed = False


class UserToken(models.Model):
    token_id   = models.AutoField(primary_key=True)
    user       = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='user_id')
    token      = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'USER_TOKENS'
        managed = False