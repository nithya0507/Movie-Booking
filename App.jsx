import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_ROOT = '/api'
const ADMIN_LOGIN_ID = 'admin_dbs'
const ADMIN_LOGIN_PASSWORD = 'DBS_mini'

const samplePosters = [
  { id: 1, title: 'Jawan', image: 'https://upload.wikimedia.org/wikipedia/en/3/39/Jawan_film_poster.jpg' },
  { id: 2, title: 'RRR', image: 'https://upload.wikimedia.org/wikipedia/en/d/d7/RRR_Poster.jpg' },
  { id: 3, title: '3 Idiots', image: 'https://upload.wikimedia.org/wikipedia/en/d/df/3_idiots_poster.jpg' },
]

function formatTime(isoTime) {
  const date = new Date(isoTime)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'UTC' })
}

function formatWallTime(isoTime) {
  if (!isoTime || typeof isoTime !== 'string') return ''
  const part = isoTime.split('T')[1]
  if (!part) return ''
  const hhmm = part.slice(0, 5)
  const [hh, mm] = hhmm.split(':').map(Number)
  if (Number.isNaN(hh) || Number.isNaN(mm)) return hhmm
  const hour12 = ((hh + 11) % 12) + 1
  const ampm = hh >= 12 ? 'PM' : 'AM'
  return `${String(hour12).padStart(2, '0')}:${String(mm).padStart(2, '0')} ${ampm}`
}

function groupSeatsByRow(seats) {
  return seats.reduce((acc, seat) => {
    if (!acc[seat.row_label]) acc[seat.row_label] = []
    acc[seat.row_label].push(seat)
    return acc
  }, {})
}

function App() {
  const [page, setPage] = useState('hello')
  const [movies, setMovies] = useState([])
  const [users, setUsers] = useState([])
  const [shows, setShows] = useState([])
  const [screens, setScreens] = useState([])
  const [theatres, setTheatres] = useState([])
  const [privateBookings, setPrivateBookings] = useState([])
  const [selectedMovie, setSelectedMovie] = useState('')
  const [selectedShow, setSelectedShow] = useState(null)
  const [seats, setSeats] = useState([])
  const [selectedSeatIds, setSelectedSeatIds] = useState([])
  const [userId, setUserId] = useState('1')
  const [loading, setLoading] = useState(true)
  const [stateMsg, setStateMsg] = useState({ type: '', message: '' })
  const [filters, setFilters] = useState({ theatre_id: '', date: '', slot: '' })
  const [adminSession, setAdminSession] = useState({ loggedIn: false, email: '', password: '' })
  const [adminCreds, setAdminCreds] = useState({ email: '', password: '' })
  const [newMovie, setNewMovie] = useState({ movie_id: '', title: '', year: '', genre: '', director: '', cast_members: '' })
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '', role: 'USER' })
  const [newShow, setNewShow] = useState({ movie_id: '', screen_id: '', show_date: '', start_time: '', end_time: '', status: 'SCHEDULED' })
  const [privateSlot, setPrivateSlot] = useState({ movie_id: '', screen_id: '', show_date: '', start_time: '', end_time: '', flat_fee: '5000' })
  const [privateBookingForm, setPrivateBookingForm] = useState({ movie_id: '', screen_id: '', booking_date: '', start_time: '', end_time: '' })
  const [showAddShowModal, setShowAddShowModal] = useState(false)
  const [showAddMovieModal, setShowAddMovieModal] = useState(false)
  const [showPrivateShowModal, setShowPrivateShowModal] = useState(false)
  const [showAddUserModal, setShowAddUserModal] = useState(false)
  const [privateReqState, setPrivateReqState] = useState({ type: '', message: '' })

  useEffect(() => {
    loadAll()
  }, [])

  const filteredShows = useMemo(() => {
    return shows.filter((show) => {
      if (show.status === 'COMPLETED') return false
      if (selectedMovie && show.movie_id !== selectedMovie) return false
      if (filters.theatre_id && String(show.screen__theatre_id) !== String(filters.theatre_id)) return false
      if (filters.date && show.show_date !== filters.date) return false
      const hour = new Date(show.start_time).getHours()
      if (filters.slot === 'MORNING' && (hour < 6 || hour >= 12)) return false
      if (filters.slot === 'AFTERNOON' && (hour < 12 || hour >= 17)) return false
      if (filters.slot === 'EVENING' && (hour < 17 || hour >= 22)) return false
      if (filters.slot === 'NIGHT' && (hour >= 6 && hour < 22)) return false
      return true
    })
  }, [shows, selectedMovie, filters])

  const seatRows = useMemo(() => groupSeatsByRow(seats), [seats])
  const seatRowsSorted = useMemo(() => {
    return Object.entries(seatRows).sort(([, rowA], [, rowB]) => {
      const maxA = Math.max(...rowA.map((seat) => Number(seat.final_price || 0)))
      const maxB = Math.max(...rowB.map((seat) => Number(seat.final_price || 0)))
      return maxB - maxA
    })
  }, [seatRows])
  const selectedSeatObjects = useMemo(() => seats.filter((s) => selectedSeatIds.includes(s.seat_id)), [seats, selectedSeatIds])
  const totalAmount = selectedSeatObjects.reduce((sum, seat) => sum + Number(seat.final_price || 0), 0)
  const privateScreens = useMemo(() => screens.filter((s) => s.screen_type === 'PRIVATE'), [screens])

  async function loadAll() {
    setLoading(true)
    try {
      const [moviesRes, usersRes, showsRes, screensRes, theatresRes, privateRes] = await Promise.all([
        fetch(`${API_ROOT}/movies/`),
        fetch(`${API_ROOT}/users/`),
        fetch(`${API_ROOT}/shows/`),
        fetch(`${API_ROOT}/screens/`),
        fetch(`${API_ROOT}/theatres/`),
        fetch(`${API_ROOT}/private-bookings/user/1/`),
      ])
      const [moviesData, usersData, showsData, screensData, theatresData, privateData] = await Promise.all([
        moviesRes.json(),
        usersRes.json(),
        showsRes.json(),
        screensRes.json(),
        theatresRes.json(),
        privateRes.json(),
      ])
      setMovies(moviesData)
      setUsers(usersData)
      setShows(showsData)
      setScreens(screensData)
      setTheatres(theatresData)
      setPrivateBookings(privateData)
      if (moviesData.length) {
        setSelectedMovie(moviesData[0].movie_id)
        setNewShow((prev) => ({ ...prev, movie_id: moviesData[0].movie_id }))
        setPrivateSlot((prev) => ({ ...prev, movie_id: moviesData[0].movie_id }))
        setPrivateBookingForm((prev) => ({ ...prev, movie_id: moviesData[0].movie_id }))
      }
      if (usersData.length) {
        setUserId(String(usersData[0].user_id))
      }
      if (screensData.length) {
        setNewShow((prev) => ({ ...prev, screen_id: String(screensData[0].screen_id) }))
      }
      const privateScreensData = screensData.filter((screen) => screen.screen_type === 'PRIVATE')
      if (privateScreensData.length) {
        setPrivateSlot((prev) => ({ ...prev, screen_id: String(privateScreensData[0].screen_id) }))
        setPrivateBookingForm((prev) => ({ ...prev, screen_id: String(privateScreensData[0].screen_id) }))
      }
    } catch {
      setStateMsg({ type: 'error', message: 'Failed to load backend data' })
    } finally {
      setLoading(false)
    }
  }

  async function openShow(show) {
    setSelectedShow(show)
    setSelectedSeatIds([])
    const res = await fetch(`${API_ROOT}/seats/${show.show_id}/`)
    const data = await res.json()
    if (Array.isArray(data)) {
      setSeats(data)
      if (data.length === 0) {
        setStateMsg({ type: 'error', message: 'No seats configured for this screen yet.' })
      }
    } else {
      setSeats([])
      setStateMsg({ type: 'error', message: data?.error || 'Failed to load seats.' })
    }
    setPage('booking')
  }

  function toggleSeat(seat) {
    if (seat.is_booked) return
    setSelectedSeatIds((prev) => (prev.includes(seat.seat_id) ? prev.filter((id) => id !== seat.seat_id) : [...prev, seat.seat_id]))
  }

  async function bookSeats() {
    const res = await fetch(`${API_ROOT}/bookings/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_id: selectedShow.show_id, seat_ids: selectedSeatIds, user_id: Number(userId) }),
    })
    const data = await res.json()
    if (!res.ok) {
      setStateMsg({ type: 'error', message: data.error || 'Booking failed' })
      return
    }
    setStateMsg({ type: 'success', message: 'Payment successful. Booking confirmed.' })
    await openShow(selectedShow)
  }

  async function loginAdmin(event) {
    event.preventDefault()
    if (adminCreds.email !== ADMIN_LOGIN_ID || adminCreds.password !== ADMIN_LOGIN_PASSWORD) {
      setStateMsg({ type: 'error', message: 'Admin login failed' })
      return
    }
    setAdminSession({ loggedIn: true, email: adminCreds.email, password: adminCreds.password })
    setStateMsg({ type: 'success', message: 'Admin logged in' })
  }

  function toIso(dateValue, timeValue) {
    return `${dateValue}T${timeValue}:00`
  }

  function getTheatreName(theatreId) {
    const theatre = theatres.find((item) => String(item.theatre_id) === String(theatreId))
    return theatre ? theatre.name : 'Unknown Theatre'
  }

  function getScreenDisplayName(screenId) {
    const screen = screens.find((item) => String(item.screen_id) === String(screenId))
    if (!screen) return `Screen ${screenId}`
    return `${screen.screen_name} - ${getTheatreName(screen.theatre_id)}`
  }

  async function addMovie(event) {
    event.preventDefault()
    const res = await fetch(`${API_ROOT}/admin/movies/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_email: adminSession.email,
        admin_password: adminSession.password,
        ...newMovie,
        year: newMovie.year ? Number(newMovie.year) : null,
      }),
    })
    const data = await res.json()
    setStateMsg({ type: res.ok ? 'success' : 'error', message: data.message || data.error })
    if (res.ok) await loadAll()
  }

  async function addShow(event) {
    event.preventDefault()
    const res = await fetch(`${API_ROOT}/admin/shows/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_email: adminSession.email,
        admin_password: adminSession.password,
        movie_id: newShow.movie_id,
        screen_id: Number(newShow.screen_id),
        show_date: newShow.show_date,
        start_time: toIso(newShow.show_date, newShow.start_time),
        end_time: toIso(newShow.show_date, newShow.end_time),
        status: newShow.status,
      }),
    })
    const data = await res.json()
    setStateMsg({ type: res.ok ? 'success' : 'error', message: data.message || data.error })
    if (res.ok) {
      setShowAddShowModal(false)
      await loadAll()
    }
  }

  async function addPrivateShow(event) {
    event.preventDefault()
    const res = await fetch(`${API_ROOT}/admin/private-shows/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_email: adminSession.email,
        admin_password: adminSession.password,
        movie_id: privateSlot.movie_id,
        screen_id: Number(privateSlot.screen_id),
        show_date: privateSlot.show_date,
        start_time: toIso(privateSlot.show_date, privateSlot.start_time),
        end_time: toIso(privateSlot.show_date, privateSlot.end_time),
        flat_fee: Number(privateSlot.flat_fee),
      }),
    })
    const data = await res.json()
    if (res.ok) {
      setStateMsg({ type: 'success', message: data.message || 'Private show added (booked by ADMIN)' })
    } else {
      setStateMsg({ type: 'error', message: data.error || 'Failed to add private show' })
    }
    if (res.ok) await loadAll()
  }

  async function addUser(event) {
    event.preventDefault()
    const res = await fetch(`${API_ROOT}/admin/users/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        admin_email: adminSession.email,
        admin_password: adminSession.password,
        ...newUser,
      }),
    })
    const data = await res.json()
    setStateMsg({ type: res.ok ? 'success' : 'error', message: data.message || data.error })
    if (res.ok) {
      setShowAddUserModal(false)
      setNewUser({ name: '', email: '', password: '', role: 'USER' })
      await loadAll()
    }
  }

  async function createPrivateBooking(event) {
    event.preventDefault()
    setPrivateReqState({ type: '', message: '' })
    const res = await fetch(`${API_ROOT}/private-bookings/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: Number(userId),
        movie_id: privateBookingForm.movie_id,
        screen_id: privateBookingForm.screen_id ? Number(privateBookingForm.screen_id) : null,
        booking_date: privateBookingForm.booking_date,
        start_time: toIso(privateBookingForm.booking_date, privateBookingForm.start_time),
        end_time: toIso(privateBookingForm.booking_date, privateBookingForm.end_time),
      }),
    })
    const data = await res.json()
    if (res.ok) {
      const details = `Private screen booked: ${data.screen_name || `Screen ${data.screen_id}`}. Slot ${formatWallTime(data.start_time)} - ${formatWallTime(data.end_time)}.`
      setPrivateReqState({ type: 'success', message: details })
      setStateMsg({ type: 'success', message: details })
    } else {
      const err = data.error || 'Private booking failed'
      setPrivateReqState({ type: 'error', message: err })
      setStateMsg({ type: 'error', message: err })
    }
    if (res.ok) {
      const privateRes = await fetch(`${API_ROOT}/private-bookings/user/${Number(userId)}/`)
      setPrivateBookings(await privateRes.json())
    }
  }

  function renderHello() {
    return (
      <section className="panel">
        <h2>Hello</h2>
        <p className="subtext">Welcome to TicketNest. Pick a section from the navigation.</p>
        <div className="poster-grid">
          {samplePosters.map((poster) => (
            <figure key={poster.id} className="poster-card">
              <img src={poster.image} alt={poster.title} />
              <figcaption>{poster.title}</figcaption>
            </figure>
          ))}
        </div>
      </section>
    )
  }

  function renderShows() {
    return (
      <section className="panel">
        <h2>Shows</h2>
        <div className="filters">
          <select className="user-input" value={selectedMovie} onChange={(e) => setSelectedMovie(e.target.value)}>
            <option value="">All Movies</option>
            {movies.map((movie) => <option key={movie.movie_id} value={movie.movie_id}>{movie.title}</option>)}
          </select>
          <select className="user-input" value={filters.theatre_id} onChange={(e) => setFilters((prev) => ({ ...prev, theatre_id: e.target.value }))}>
            <option value="">All Theatres</option>
            {theatres.map((t) => <option key={t.theatre_id} value={t.theatre_id}>{t.name}</option>)}
          </select>
          <input className="user-input" type="date" value={filters.date} onChange={(e) => setFilters((prev) => ({ ...prev, date: e.target.value }))} />
          <select className="user-input" value={filters.slot} onChange={(e) => setFilters((prev) => ({ ...prev, slot: e.target.value }))}>
            <option value="">All Time Slots</option>
            <option value="MORNING">Morning</option>
            <option value="AFTERNOON">Afternoon</option>
            <option value="EVENING">Evening</option>
            <option value="NIGHT">Night</option>
          </select>
        </div>
        <div className="show-grid">
          {filteredShows.map((show) => (
            <button key={show.show_id} className="show-pill" onClick={() => openShow(show)}>
              <strong>{show.movie__title || show.movie_id}</strong>
              <span>{show.show_date} | {formatTime(show.start_time)} - {formatTime(show.end_time)}</span>
              <small>{getScreenDisplayName(show.screen_id)}</small>
            </button>
          ))}
          {!filteredShows.length && <p className="empty-state">No shows for this filter set.</p>}
        </div>
      </section>
    )
  }

  function renderBooking() {
    if (!selectedShow) return <section className="panel"><p className="empty-state">Choose a show first from Shows page.</p></section>
    return (
      <section className="layout-grid">
        <article className="panel seat-panel">
          <h2>Seat Selection</h2>
          <div className="screen-indicator">SCREEN THIS WAY</div>
          <div className="seat-layout">
            {seatRowsSorted.map(([rowLabel, rowSeats]) => (
              <div className="seat-row" key={rowLabel}>
                <span className="row-label">{rowLabel}</span>
                <div className="row-seats">
                  {rowSeats.map((seat) => (
                    <button
                      type="button"
                      key={seat.seat_id}
                      className={`seat ${seat.is_booked ? 'booked' : selectedSeatIds.includes(seat.seat_id) ? 'selected' : 'available'}`}
                      disabled={seat.is_booked}
                      onClick={() => toggleSeat(seat)}
                    >
                      <span className="seat-number">{seat.seat_number}</span>
                      <span className="seat-type-tag">{seat.seat_type}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </article>
        <aside className="panel summary-panel">
          <h2>Booking Summary</h2>
          <select className="user-input" value={userId} onChange={(e) => setUserId(e.target.value)}>
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.user_id} - {u.name || u.email || 'User'}
              </option>
            ))}
          </select>
          <p><strong>Show:</strong> {formatTime(selectedShow.start_time)}</p>
          <p><strong>Seats:</strong> {selectedSeatObjects.map((s) => `${s.row_label}${s.seat_number}`).join(', ') || '-'}</p>
          <p><strong>Total:</strong> Rs. {totalAmount.toFixed(2)}</p>
          <button className="book-btn" onClick={bookSeats} disabled={!selectedSeatIds.length}>Pay & Confirm</button>
        </aside>
      </section>
    )
  }

  function renderPrivateBooking() {
    return (
      <section className="admin-layout">
        <article className="panel">
          <h2>Private Booking</h2>
          <form className="admin-form" onSubmit={createPrivateBooking}>
            <select className="user-input" value={userId} onChange={(e) => setUserId(e.target.value)}>
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id} - {u.name || u.email || 'User'}
                </option>
              ))}
            </select>
            <select className="user-input" value={privateBookingForm.movie_id} onChange={(e) => setPrivateBookingForm((p) => ({ ...p, movie_id: e.target.value }))}>
              {movies.map((m) => <option key={m.movie_id} value={m.movie_id}>{m.title}</option>)}
            </select>
            <select className="user-input" value={privateBookingForm.screen_id} onChange={(e) => setPrivateBookingForm((p) => ({ ...p, screen_id: e.target.value }))}>
              <option value="">Auto-assign private screen</option>
              {privateScreens.map((screen) => (
                <option key={screen.screen_id} value={screen.screen_id}>
                  {getScreenDisplayName(screen.screen_id)}
                </option>
              ))}
            </select>
            <input className="user-input" type="date" value={privateBookingForm.booking_date} onChange={(e) => setPrivateBookingForm((p) => ({ ...p, booking_date: e.target.value }))} required />
            <div className="input-row">
              <input className="user-input" type="time" value={privateBookingForm.start_time} onChange={(e) => setPrivateBookingForm((p) => ({ ...p, start_time: e.target.value }))} required />
              <input className="user-input" type="time" value={privateBookingForm.end_time} onChange={(e) => setPrivateBookingForm((p) => ({ ...p, end_time: e.target.value }))} required />
            </div>
            <button className="book-btn" type="submit">Request Private Screen</button>
          </form>
          {privateReqState.message && <p className={`feedback ${privateReqState.type}`}>{privateReqState.message}</p>}
          <p className="subtext">Available private screens:</p>
          <div className="show-grid">
            {privateScreens.map((screen) => (
              <div key={screen.screen_id} className="show-pill">
                <strong>{screen.screen_name}</strong>
                <small>{getTheatreName(screen.theatre_id)}</small>
              </div>
            ))}
            {!privateScreens.length && <p className="empty-state">No private screens configured.</p>}
          </div>
        </article>
        <article className="panel">
          <h2>Your Private Bookings</h2>
          <div className="show-grid">
            {privateBookings.map((pb) => (
              <div key={pb.private_booking_id} className="show-pill">
                <strong>{pb.movie_title}</strong>
                <span>{pb.booking_date}</span>
                <small>{formatWallTime(pb.start_time)} - {formatWallTime(pb.end_time)}</small>
              </div>
            ))}
            {!privateBookings.length && <p className="empty-state">No private bookings yet.</p>}
          </div>
        </article>
      </section>
    )
  }

  function renderAdmin() {
    if (!adminSession.loggedIn) {
      return (
        <section className="admin-layout">
          <article className="panel">
            <h2>Admin Login</h2>
            <form className="admin-form" onSubmit={loginAdmin}>
              <input className="user-input" value={adminCreds.email} placeholder="Admin ID" onChange={(e) => setAdminCreds((p) => ({ ...p, email: e.target.value }))} />
              <input className="user-input" type="password" value={adminCreds.password} placeholder="Password" onChange={(e) => setAdminCreds((p) => ({ ...p, password: e.target.value }))} />
              <button className="book-btn" type="submit">Login</button>
            </form>
            <p className="empty-state">Login required for admin actions.</p>
          </article>
        </section>
      )
    }

    return (
      <section className="admin-layout">
        <article className="panel">
          <h2>Admin Home</h2>
          <form className="admin-form" onSubmit={loginAdmin}>
            <input className="user-input" value={adminCreds.email} placeholder="Admin ID" onChange={(e) => setAdminCreds((p) => ({ ...p, email: e.target.value }))} />
            <input className="user-input" type="password" value={adminCreds.password} placeholder="Password" onChange={(e) => setAdminCreds((p) => ({ ...p, password: e.target.value }))} />
            <button className="book-btn" type="submit">Login</button>
          </form>
          <button className="book-btn" type="button" onClick={() => setShowAddShowModal(true)}>
            Add Show
          </button>
          <button className="book-btn" type="button" onClick={() => setShowAddMovieModal(true)}>
            Add Movie
          </button>
          <button className="book-btn" type="button" onClick={() => setShowPrivateShowModal(true)}>
            Add Private Screen Show
          </button>
          <button className="book-btn" type="button" onClick={() => setShowAddUserModal(true)}>
            Add User
          </button>
        </article>
        {showAddMovieModal && (
          <article className="panel modal-panel">
            <h2>Add Movie</h2>
            <form className="admin-form" onSubmit={addMovie}>
              <input className="user-input" placeholder="Movie ID (tt...)" value={newMovie.movie_id} onChange={(e) => setNewMovie((p) => ({ ...p, movie_id: e.target.value }))} required />
              <input className="user-input" placeholder="Title" value={newMovie.title} onChange={(e) => setNewMovie((p) => ({ ...p, title: e.target.value }))} required />
              <input className="user-input" placeholder="Year" value={newMovie.year} onChange={(e) => setNewMovie((p) => ({ ...p, year: e.target.value }))} />
              <input className="user-input" placeholder="Genre" value={newMovie.genre} onChange={(e) => setNewMovie((p) => ({ ...p, genre: e.target.value }))} />
              <input className="user-input" placeholder="Director" value={newMovie.director} onChange={(e) => setNewMovie((p) => ({ ...p, director: e.target.value }))} />
              <input className="user-input" placeholder="Cast" value={newMovie.cast_members} onChange={(e) => setNewMovie((p) => ({ ...p, cast_members: e.target.value }))} />
              <button className="book-btn" type="submit" disabled={!adminSession.loggedIn}>Save Movie</button>
              <button className="mode-btn" type="button" onClick={() => setShowAddMovieModal(false)}>Close</button>
            </form>
          </article>
        )}
        {showPrivateShowModal && (
          <article className="panel modal-panel">
            <h2>Add Private Screen Show</h2>
            <p className="subtext">Allowed only when slot is free and date is at least 1 day ahead.</p>
            <form className="admin-form" onSubmit={addPrivateShow}>
              <select className="user-input" value={privateSlot.movie_id} onChange={(e) => setPrivateSlot((p) => ({ ...p, movie_id: e.target.value }))}>{movies.map((m) => <option key={m.movie_id} value={m.movie_id}>{m.title}</option>)}</select>
              <select className="user-input" value={privateSlot.screen_id} onChange={(e) => setPrivateSlot((p) => ({ ...p, screen_id: e.target.value }))}>{privateScreens.map((s) => <option key={s.screen_id} value={s.screen_id}>{getScreenDisplayName(s.screen_id)}</option>)}</select>
              <input className="user-input" type="date" value={privateSlot.show_date} onChange={(e) => setPrivateSlot((p) => ({ ...p, show_date: e.target.value }))} required />
              <div className="input-row">
                <input className="user-input" type="time" value={privateSlot.start_time} onChange={(e) => setPrivateSlot((p) => ({ ...p, start_time: e.target.value }))} required />
                <input className="user-input" type="time" value={privateSlot.end_time} onChange={(e) => setPrivateSlot((p) => ({ ...p, end_time: e.target.value }))} required />
              </div>
              <input className="user-input" type="number" value={privateSlot.flat_fee} onChange={(e) => setPrivateSlot((p) => ({ ...p, flat_fee: e.target.value }))} />
              <button className="book-btn" type="submit" disabled={!adminSession.loggedIn}>Save Private Show</button>
              <button className="mode-btn" type="button" onClick={() => setShowPrivateShowModal(false)}>Close</button>
            </form>
          </article>
        )}
        {showAddUserModal && (
          <article className="panel modal-panel">
            <h2>Add User</h2>
            <form className="admin-form" onSubmit={addUser}>
              <input className="user-input" placeholder="Name" value={newUser.name} onChange={(e) => setNewUser((p) => ({ ...p, name: e.target.value }))} required />
              <input className="user-input" placeholder="Email" value={newUser.email} onChange={(e) => setNewUser((p) => ({ ...p, email: e.target.value }))} required />
              <input className="user-input" type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser((p) => ({ ...p, password: e.target.value }))} required />
              <select className="user-input" value={newUser.role} onChange={(e) => setNewUser((p) => ({ ...p, role: e.target.value }))}>
                <option value="USER">USER</option>
                <option value="ADMIN">ADMIN</option>
              </select>
              <button className="book-btn" type="submit" disabled={!adminSession.loggedIn}>Save User</button>
              <button className="mode-btn" type="button" onClick={() => setShowAddUserModal(false)}>Close</button>
            </form>
          </article>
        )}
        {showAddShowModal && (
          <article className="panel modal-panel">
            <h2>Add Show</h2>
            <form className="admin-form" onSubmit={addShow}>
              <select className="user-input" value={newShow.movie_id} onChange={(e) => setNewShow((p) => ({ ...p, movie_id: e.target.value }))}>{movies.map((m) => <option key={m.movie_id} value={m.movie_id}>{m.title}</option>)}</select>
              <select className="user-input" value={newShow.screen_id} onChange={(e) => setNewShow((p) => ({ ...p, screen_id: e.target.value }))}>{screens.map((s) => <option key={s.screen_id} value={s.screen_id}>{getScreenDisplayName(s.screen_id)}</option>)}</select>
              <input className="user-input" type="date" value={newShow.show_date} onChange={(e) => setNewShow((p) => ({ ...p, show_date: e.target.value }))} required />
              <div className="input-row">
                <input className="user-input" type="time" value={newShow.start_time} onChange={(e) => setNewShow((p) => ({ ...p, start_time: e.target.value }))} required />
                <input className="user-input" type="time" value={newShow.end_time} onChange={(e) => setNewShow((p) => ({ ...p, end_time: e.target.value }))} required />
              </div>
              <button className="book-btn" type="submit" disabled={!adminSession.loggedIn}>Save Show</button>
              <button className="mode-btn" type="button" onClick={() => setShowAddShowModal(false)}>Close</button>
            </form>
          </article>
        )}
      </section>
    )
  }

  if (loading) return <main className="app-shell"><section className="loading-card">Loading...</section></main>

  return (
    <main className="app-shell">
      <header className="hero">
        <p className="eyebrow">Movie Booking System</p>
        <h1>TicketNest</h1>
        <p className="hero-copy">Book tickets, browse shows, and manage private screens.</p>
        <div className="mode-switch">
          {['hello', 'shows', 'booking', 'private', 'admin'].map((name) => (
            <button key={name} className={`mode-btn ${page === name ? 'active' : ''}`} onClick={() => setPage(name)}>
              {name === 'hello' ? 'Hello' : name === 'shows' ? 'Shows' : name === 'booking' ? 'Booking' : name === 'private' ? 'Private Booking' : 'Admin'}
            </button>
          ))}
        </div>
      </header>
      {stateMsg.message && <p className={`feedback ${stateMsg.type}`}>{stateMsg.message}</p>}
      {page === 'hello' && renderHello()}
      {page === 'shows' && renderShows()}
      {page === 'booking' && renderBooking()}
      {page === 'private' && renderPrivateBooking()}
      {page === 'admin' && renderAdmin()}
    </main>
  )
}

export default App
