/**
 * Neural Network Audio Visualizer for AI Tutor Platform
 * "The Living Mind" - Real-time audio-reactive particle system
 * 
 * Features:
 * - Full-screen neural network particle background
 * - Web Audio API integration for audio reactivity
 * - Mouse interaction (magnetic field effect)
 * - Chat input reactivity (color shifting and acceleration)
 * - Waveform visualization
 * - High-performance optimized rendering
 */

class NeuralVisualizer {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.particles = [];
        this.mouse = { x: null, y: null, radius: 150 };
        this.particleCount = 100;

        // Audio properties
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.bufferLength = 0;
        this.audioElement = null;
        this.audioInitialized = false;

        // State
        this.isActive = true;
        this.chatInputActive = false;
        this.bassIntensity = 0;

        // Animation
        this.animationFrame = null;

        this.init();
    }

    init() {
        this.createCanvas();
        this.createParticles();
        this.setupEventListeners();
        this.animate();
    }

    createCanvas() {
        // Create canvas element
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'neural-canvas';
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.zIndex = '-1';
        this.canvas.style.pointerEvents = 'none';

        document.body.insertBefore(this.canvas, document.body.firstChild);

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
    }

    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        this.particles = [];

        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                baseX: Math.random() * this.canvas.width,
                baseY: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                size: Math.random() * 2 + 1,
                baseSize: Math.random() * 2 + 1,
                color: this.getParticleColor(0)
            });
        }
    }

    getParticleColor(intensity = 0) {
        // Base color: Blue (hue: 220)
        // Active color: Purple (hue: 280)
        const baseHue = 220;
        const activeHue = 280;
        const hue = baseHue + (activeHue - baseHue) * intensity;
        const saturation = 70 + intensity * 20;
        const lightness = 50 + intensity * 10;

        return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    }

    setupEventListeners() {
        // Mouse movement
        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.x;
            this.mouse.y = e.y;
        });

        // Mouse leave
        window.addEventListener('mouseout', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });

        // Window resize
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            // Recreate particles with new dimensions
            this.createParticles();
        });

        // Page visibility (pause when tab is inactive)
        document.addEventListener('visibilitychange', () => {
            this.isActive = !document.hidden;
        });

        // Chat input reactivity
        const chatInput = document.getElementById('question-input');
        if (chatInput) {
            chatInput.addEventListener('input', () => {
                this.chatInputActive = true;
                this.activateChatEffect();
            });

            chatInput.addEventListener('blur', () => {
                setTimeout(() => {
                    this.chatInputActive = false;
                }, 2000);
            });
        }

        // Audio element detection and initialization
        this.detectAudioElement();
    }

    activateChatEffect() {
        // Temporarily boost particle movement and change colors
        this.particles.forEach(particle => {
            particle.vx *= 1.5;
            particle.vy *= 1.5;
        });

        // Reset after 1 second
        setTimeout(() => {
            this.particles.forEach(particle => {
                particle.vx *= 0.67;
                particle.vy *= 0.67;
            });
        }, 1000);
    }

    detectAudioElement() {
        // Wait for DOM to be ready
        const findAudio = () => {
            this.audioElement = document.querySelector('audio');

            if (this.audioElement) {
                this.initAudio();
            } else {
                // Try again after a short delay
                setTimeout(findAudio, 500);
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', findAudio);
        } else {
            findAudio();
        }
    }

    initAudio() {
        if (this.audioInitialized) return;

        try {
            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();

            // Configure analyser
            this.analyser.fftSize = 256;
            this.bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(this.bufferLength);

            // Connect audio source
            const source = this.audioContext.createMediaElementSource(this.audioElement);
            source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            this.audioInitialized = true;

            // Handle autoplay policy - resume on user interaction
            const resumeAudio = () => {
                if (this.audioContext.state === 'suspended') {
                    this.audioContext.resume();
                }
            };

            this.audioElement.addEventListener('play', resumeAudio);
            document.addEventListener('click', resumeAudio, { once: true });

        } catch (error) {
            console.warn('Web Audio API initialization failed:', error);
        }
    }

    updateParticles() {
        const chatIntensity = this.chatInputActive ? 0.7 : 0;
        const audioIntensity = this.bassIntensity;
        const totalIntensity = Math.max(chatIntensity, audioIntensity);

        this.particles.forEach(particle => {
            // Mouse interaction (magnetic field)
            if (this.mouse.x !== null && this.mouse.y !== null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.mouse.radius) {
                    const force = (this.mouse.radius - distance) / this.mouse.radius;
                    const angle = Math.atan2(dy, dx);

                    // Push particles away from mouse
                    particle.vx -= Math.cos(angle) * force * 0.5;
                    particle.vy -= Math.sin(angle) * force * 0.5;
                }
            }

            // Return to base position (spring effect)
            const dx = particle.baseX - particle.x;
            const dy = particle.baseY - particle.y;
            particle.vx += dx * 0.001;
            particle.vy += dy * 0.001;

            // Apply velocity with intensity boost
            const speedMultiplier = 1 + totalIntensity;
            particle.x += particle.vx * speedMultiplier;
            particle.y += particle.vy * speedMultiplier;

            // Damping
            particle.vx *= 0.95;
            particle.vy *= 0.95;

            // Update size based on audio
            particle.size = particle.baseSize * (1 + audioIntensity * 2);

            // Update color
            particle.color = this.getParticleColor(totalIntensity);

            // Wrap around edges
            if (particle.x < 0) particle.x = this.canvas.width;
            if (particle.x > this.canvas.width) particle.x = 0;
            if (particle.y < 0) particle.y = this.canvas.height;
            if (particle.y > this.canvas.height) particle.y = 0;
        });
    }

    drawParticles() {
        // Clear canvas
        this.ctx.fillStyle = 'rgba(249, 250, 251, 0.1)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw connections
        this.ctx.strokeStyle = 'rgba(100, 100, 255, 0.1)';
        this.ctx.lineWidth = 0.5;

        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 120) {
                    const opacity = (1 - distance / 120) * 0.3;
                    this.ctx.strokeStyle = `rgba(100, 100, 255, ${opacity})`;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.stroke();
                }
            }
        }

        // Draw particles
        this.particles.forEach(particle => {
            this.ctx.fillStyle = particle.color;
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fill();

            // Glow effect
            const gradient = this.ctx.createRadialGradient(
                particle.x, particle.y, 0,
                particle.x, particle.y, particle.size * 3
            );
            gradient.addColorStop(0, particle.color.replace(')', ', 0.3)').replace('hsl', 'hsla'));
            gradient.addColorStop(1, particle.color.replace(')', ', 0)').replace('hsl', 'hsla'));

            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size * 3, 0, Math.PI * 2);
            this.ctx.fill();
        });
    }

    analyzeAudio() {
        if (!this.audioInitialized || !this.analyser) return;

        try {
            this.analyser.getByteFrequencyData(this.dataArray);

            // Calculate bass intensity (lower frequencies)
            let bassSum = 0;
            const bassRange = Math.floor(this.bufferLength * 0.15); // Lower 15% of frequencies

            for (let i = 0; i < bassRange; i++) {
                bassSum += this.dataArray[i];
            }

            // Normalize bass intensity (0 to 1)
            this.bassIntensity = (bassSum / (bassRange * 255)) * 1.5;
            this.bassIntensity = Math.min(this.bassIntensity, 1);

        } catch (error) {
            console.warn('Audio analysis error:', error);
        }
    }

    drawWaveform() {
        if (!this.audioInitialized || !this.analyser) return;

        try {
            // Get waveform data
            const waveformData = new Uint8Array(this.bufferLength);
            this.analyser.getByteTimeDomainData(waveformData);

            // Draw waveform at bottom of screen
            this.ctx.lineWidth = 2;
            this.ctx.strokeStyle = `hsla(220, 70%, 60%, ${0.3 + this.bassIntensity * 0.5})`;
            this.ctx.beginPath();

            const sliceWidth = this.canvas.width / this.bufferLength;
            let x = 0;
            const baseY = this.canvas.height - 80;
            const amplitude = 30;

            for (let i = 0; i < this.bufferLength; i++) {
                const v = waveformData[i] / 128.0;
                const y = baseY + (v - 1) * amplitude;

                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }

                x += sliceWidth;
            }

            this.ctx.stroke();

        } catch (error) {
            console.warn('Waveform drawing error:', error);
        }
    }

    animate() {
        if (!this.isActive) {
            // Continue animation loop but don't render
            this.animationFrame = requestAnimationFrame(() => this.animate());
            return;
        }

        // Analyze audio
        this.analyzeAudio();

        // Update particles
        this.updateParticles();

        // Draw everything
        this.drawParticles();
        this.drawWaveform();

        // Continue animation loop
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }

    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.neuralVisualizer = new NeuralVisualizer();
    });
} else {
    window.neuralVisualizer = new NeuralVisualizer();
}
