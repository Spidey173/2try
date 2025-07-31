document.addEventListener('DOMContentLoaded', function() {
    // Player elements
    const audioPlayer = new Audio();
    const playButton = document.getElementById('playButton');
    const likeButton = document.getElementById('likeButton');
    const volumeControl = document.getElementById('volumeControl');
    const seekBar = document.getElementById('seekBar');
    const currentTimeDisplay = document.getElementById('currentTime');
    const durationDisplay = document.getElementById('duration');
    const nowPlayingTitle = document.getElementById('nowPlayingTitle');
    const nowPlayingArtist = document.getElementById('nowPlayingArtist');
    const nowPlayingImg = document.getElementById('nowPlayingImg');

    // Player state
    let currentSongId = localStorage.getItem('currentSongId') || null;
    let isPlaying = localStorage.getItem('isPlaying') === 'true' || false;
    let currentTime = parseFloat(localStorage.getItem('currentTime')) || 0;
    let volume = parseFloat(localStorage.getItem('volume')) || 0.7;
    let queue = JSON.parse(localStorage.getItem('queue')) || [];
    let queuePosition = parseInt(localStorage.getItem('queuePosition')) || 0;
    let isLoadingNewSong = false;

    // Initialize player
    function initPlayer() {
        // Set initial volume
        audioPlayer.volume = volume;
        volumeControl.value = volume;
        
        // Restore playback state if a song was playing
        if (currentSongId) {
            // Only load metadata if not already loaded
            if (!nowPlayingTitle.textContent || nowPlayingTitle.textContent === 'Not Playing') {
                loadSongData(currentSongId, false);
            }
            
            // Restore playback position if not loading a new song
            if (!isLoadingNewSong) {
                audioPlayer.currentTime = currentTime;
            }
            
            if (isPlaying) {
                // Small timeout to ensure audio element is ready
                setTimeout(() => {
                    audioPlayer.play().catch(e => console.log('Autoplay prevented:', e));
                }, 100);
            }
            updatePlayButton();
        }
        
        // Check if song is liked
        if (currentSongId) {
            checkLikeStatus(currentSongId);
        }
    }

    // Load song data and update UI
    function loadSongData(songId, shouldPlay = true) {
        // If same song is clicked, just restart it
        if (songId === currentSongId) {
            audioPlayer.currentTime = 0;
            if (shouldPlay) {
                audioPlayer.play()
                    .then(() => {
                        isPlaying = true;
                        localStorage.setItem('isPlaying', true);
                        updatePlayButton();
                    })
                    .catch(err => console.error('Playback error:', err));
            }
            return;
        }

        isLoadingNewSong = true;
        fetch(`/song-data/${songId}`)
            .then(response => response.json())
            .then(song => {
                nowPlayingTitle.textContent = song.title;
                nowPlayingArtist.textContent = song.artist;
                nowPlayingImg.src = song.cover_url || `https://source.unsplash.com/random/60x60/?music,album&sig=${song.id}`;
                
                // Store current song in state
                currentSongId = song.id;
                localStorage.setItem('currentSongId', currentSongId);

                // If the song URL changed, load the new source
                if (audioPlayer.src !== song.url) {
                    audioPlayer.src = song.url;
                }

                // Add to queue if not already there
                if (!queue.some(s => s.id === song.id)) {
                    queue.push({ id: song.id, title: song.title, artist: song.artist });
                    localStorage.setItem('queue', JSON.stringify(queue));
                }
                
                // Update queue position
                queuePosition = queue.findIndex(s => s.id === song.id);
                localStorage.setItem('queuePosition', queuePosition);

                if (shouldPlay) {
                    audioPlayer.play()
                        .then(() => {
                            isPlaying = true;
                            localStorage.setItem('isPlaying', true);
                            updatePlayButton();
                        })
                        .catch(err => console.error('Playback error:', err));
                }

                // Check like status for the new song
                checkLikeStatus(song.id);
            })
            .finally(() => {
                isLoadingNewSong = false;
            });
    }

    // Play song function (called when clicking on a song card)
    function playSong(songId) {
        loadSongData(songId);
    }

    // Toggle play/pause
    function togglePlay() {
        if (audioPlayer.paused) {
            if (!audioPlayer.src && currentSongId) {
                // If no source but we have a song ID, load it
                loadSongData(currentSongId);
            }
            audioPlayer.play()
                .then(() => {
                    isPlaying = true;
                    localStorage.setItem('isPlaying', true);
                    updatePlayButton();
                });
        } else {
            audioPlayer.pause();
            isPlaying = false;
            localStorage.setItem('isPlaying', false);
            updatePlayButton();
        }
    }

    // Update play button icon based on state
    function updatePlayButton() {
        if (playButton) {
            playButton.innerHTML = isPlaying ? 
                '<i class="bi bi-pause-fill fs-5"></i>' : 
                '<i class="bi bi-play-fill fs-5"></i>';
        }
    }

    // Skip forward 10 seconds
    function skipForward() {
        audioPlayer.currentTime = Math.min(audioPlayer.currentTime + 10, audioPlayer.duration);
    }

    // Skip backward 10 seconds
    function skipBackward() {
        audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 10);
    }

    // Play next song in queue
    function nextSong() {
        if (queue.length === 0) {
            // No songs in queue - stop playback
            audioPlayer.pause();
            isPlaying = false;
            localStorage.setItem('isPlaying', false);
            updatePlayButton();
            return;
        }
        
        // Try to get next song from server first
        fetch(`/next/${currentSongId || 0}`, { method: 'POST' })
            .then(response => response.json())
            .then(song => {
                if (song && song.id) {
                    playSong(song.id);
                } else {
                    // Fallback to local queue
                    queuePosition = (queuePosition + 1) % queue.length;
                    localStorage.setItem('queuePosition', queuePosition);
                    playSong(queue[queuePosition].id);
                }
            })
            .catch(() => {
                // If API fails, use local queue
                queuePosition = (queuePosition + 1) % queue.length;
                localStorage.setItem('queuePosition', queuePosition);
                playSong(queue[queuePosition].id);
            });
    }

    // Play previous song in queue
    function prevSong() {
        if (queue.length === 0) {
            // No songs in queue - stop playback
            audioPlayer.pause();
            isPlaying = false;
            localStorage.setItem('isPlaying', false);
            updatePlayButton();
            return;
        }
        
        // Try to get previous song from server first
        fetch(`/prev/${currentSongId || 0}`, { method: 'POST' })
            .then(response => response.json())
            .then(song => {
                if (song && song.id) {
                    playSong(song.id);
                } else {
                    // Fallback to local queue
                    queuePosition = (queuePosition - 1 + queue.length) % queue.length;
                    localStorage.setItem('queuePosition', queuePosition);
                    playSong(queue[queuePosition].id);
                }
            })
            .catch(() => {
                // If API fails, use local queue
                queuePosition = (queuePosition - 1 + queue.length) % queue.length;
                localStorage.setItem('queuePosition', queuePosition);
                playSong(queue[queuePosition].id);
            });
    }

    // Check if current song is liked and update button
    function checkLikeStatus(songId) {
        if (!songId) return;
        
        fetch(`/like-status/${songId}`)
            .then(response => response.json())
            .then(data => {
                if (likeButton) {
                    likeButton.classList.toggle('liked', data.liked);
                    const icon = likeButton.querySelector('i');
                    icon.className = data.liked ? 
                        'bi bi-heart-fill fs-5' : 
                        'bi bi-heart fs-5';
                }
            });
    }

    // Toggle like status
    function toggleLike() {
        if (!currentSongId) return;
        
        fetch(`/like/${currentSongId}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (likeButton) {
                    likeButton.classList.toggle('liked', data.liked);
                    const icon = likeButton.querySelector('i');
                    icon.className = data.liked ? 
                        'bi bi-heart-fill fs-5' : 
                        'bi bi-heart fs-5';
                }
            });
    }

    // Format time as MM:SS
    function formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    // Initialize event listeners
    function initEventListeners() {
        // Save current time periodically
        audioPlayer.addEventListener('timeupdate', () => {
            if (!isNaN(audioPlayer.duration)) {
                seekBar.value = (audioPlayer.currentTime / audioPlayer.duration) * 100;
                currentTimeDisplay.textContent = formatTime(audioPlayer.currentTime);
                
                // Save current time every second
                if (Math.floor(audioPlayer.currentTime) % 1 === 0) {
                    localStorage.setItem('currentTime', audioPlayer.currentTime);
                }
            }
        });

        // When metadata is loaded
        audioPlayer.addEventListener('loadedmetadata', () => {
            if (!isNaN(audioPlayer.duration)) {
                durationDisplay.textContent = formatTime(audioPlayer.duration);
                seekBar.max = 100;
            }
        });

        // Seek bar interaction
        seekBar.addEventListener('input', () => {
            const seekTime = (seekBar.value / 100) * audioPlayer.duration;
            audioPlayer.currentTime = seekTime;
        });

        // Volume control
        volumeControl.addEventListener('input', () => {
            audioPlayer.volume = volumeControl.value;
            localStorage.setItem('volume', volumeControl.value);
        });

        // When song ends
        audioPlayer.addEventListener('ended', () => {
            nextSong();
        });

        // Handle page visibility changes (for browser back/forward)
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                // Restore playback state when returning to the page
                initPlayer();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                togglePlay();
            } else if (e.code === 'ArrowRight') {
                skipForward();
            } else if (e.code === 'ArrowLeft') {
                skipBackward();
            } else if (e.code === 'ArrowUp') {
                volumeControl.value = Math.min(1, parseFloat(volumeControl.value) + 0.1);
                volumeControl.dispatchEvent(new Event('input'));
            } else if (e.code === 'ArrowDown') {
                volumeControl.value = Math.max(0, parseFloat(volumeControl.value) - 0.1);
                volumeControl.dispatchEvent(new Event('input'));
            }
        });
    }

    // Initialize everything
    initEventListeners();
    initPlayer();

    // Expose functions to global scope for HTML onclick handlers
    window.playSong = playSong;
    window.togglePlay = togglePlay;
    window.skipForward = skipForward;
    window.skipBackward = skipBackward;
    window.nextSong = nextSong;
    window.prevSong = prevSong;
    window.toggleLike = toggleLike;

    // Special handling for browser back/forward navigation
    window.addEventListener('pageshow', function(event) {
        if (event.persisted) {
            initPlayer();
        }
    });
});
