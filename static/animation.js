/**
 * Neural Mind Background Animation
 * A stunning particle network animation with mouse interaction and typing reactivity
 */

class NeuralAnimation {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.particles = [];
        this.mouse = { x: null, y: null, radius: 150 };
        this.animationId = null;

        // Typing detection
        this.lastKeyTime = 0;
        this.typingSpeed = 0;
        this.isTyping = false;

        // Colors
        this.colors = {
            normal: { r: 102, g: 126, b: 234 }, // Deep Blue #667eea
            typing: { r: 236, g: 72, b: 153 },  // Hot Pink #ec4899
            particle: 'rgba(102, 126, 234, 0.8)',
            connection: 'rgba(124, 58, 162, 0.2)',
            glow: 'rgba(139, 92, 246, 0.3)'
        };

        this.init();
    }

    init() {
        // Create canvas
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
        this.resize();

        // Create particles
        this.createParticles();

        // Event listeners
        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        window.addEventListener('mouseout', () => this.handleMouseOut());

        // Listen to ALL input fields for typing
        this.setupTypingListeners();

        // Start animation
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        const particleCount = Math.min(100, Math.floor((this.canvas.width * this.canvas.height) / 10000));

        for (let i = 0; i < particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1,
                originalVx: (Math.random() - 0.5) * 0.5,
                originalVy: (Math.random() - 0.5) * 0.5
            });
        }
    }

    setupTypingListeners() {
        // Find all input and textarea elements
        const inputs = document.querySelectorAll('input[type="text"], textarea');

        inputs.forEach(input => {
            input.addEventListener('input', () => this.handleTyping());
        });

        // Also listen for any future inputs (using delegation)
        document.addEventListener('input', (e) => {
            if (e.target.matches('input[type="text"], textarea')) {
                this.handleTyping();
            }
        });
    }

    handleTyping() {
        const now = Date.now();
        const timeDiff = now - this.lastKeyTime;

        // Calculate typing speed (lower = faster)
        this.typingSpeed = Math.max(0, Math.min(1, 1 - (timeDiff / 300)));
        this.isTyping = true;

        this.lastKeyTime = now;

        // Reset typing state after delay
        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            this.isTyping = false;
            this.typingSpeed = 0;
        }, 500);
    }

    handleMouseMove(e) {
        this.mouse.x = e.clientX;
        this.mouse.y = e.clientY;
    }

    handleMouseOut() {
        this.mouse.x = null;
        this.mouse.y = null;
    }

    drawParticle(particle, color) {
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        this.ctx.fillStyle = color;
        this.ctx.fill();

        // Add glow effect when typing
        if (this.isTyping && this.typingSpeed > 0.3) {
            this.ctx.shadowBlur = 10 * this.typingSpeed;
            this.ctx.shadowColor = color;
        }
    }

    drawConnection(p1, p2, distance, maxDistance) {
        const opacity = 1 - (distance / maxDistance);

        // Color shift based on typing
        let color;
        if (this.isTyping && this.typingSpeed > 0.2) {
            const mix = this.typingSpeed;
            const r = Math.floor(this.colors.normal.r * (1 - mix) + this.colors.typing.r * mix);
            const g = Math.floor(this.colors.normal.g * (1 - mix) + this.colors.typing.g * mix);
            const b = Math.floor(this.colors.normal.b * (1 - mix) + this.colors.typing.b * mix);
            color = `rgba(${r}, ${g}, ${b}, ${opacity * 0.3})`;
        } else {
            color = `rgba(124, 58, 162, ${opacity * 0.2})`;
        }

        this.ctx.beginPath();
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 0.5;
        this.ctx.moveTo(p1.x, p1.y);
        this.ctx.lineTo(p2.x, p2.y);
        this.ctx.stroke();
    }

    drawMouseGlow() {
        if (this.mouse.x === null || this.mouse.y === null) return;

        const gradient = this.ctx.createRadialGradient(
            this.mouse.x, this.mouse.y, 0,
            this.mouse.x, this.mouse.y, this.mouse.radius
        );

        gradient.addColorStop(0, 'rgba(139, 92, 246, 0.15)');
        gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.05)');
        gradient.addColorStop(1, 'rgba(139, 92, 246, 0)');

        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    updateParticle(particle) {
        // Mouse interaction - repulsion/attraction
        if (this.mouse.x !== null && this.mouse.y !== null) {
            const dx = particle.x - this.mouse.x;
            const dy = particle.y - this.mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < this.mouse.radius) {
                const force = (this.mouse.radius - distance) / this.mouse.radius;
                const angle = Math.atan2(dy, dx);

                // Repulsion
                particle.vx += Math.cos(angle) * force * 0.5;
                particle.vy += Math.sin(angle) * force * 0.5;
            }
        }

        // Typing speed effect - accelerate particles
        if (this.isTyping && this.typingSpeed > 0.3) {
            const speedBoost = 1 + (this.typingSpeed * 3);
            particle.vx *= speedBoost;
            particle.vy *= speedBoost;
        }

        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;

        // Damping - slow down gradually
        particle.vx *= 0.95;
        particle.vy *= 0.95;

        // Restore to original speed if too slow
        if (Math.abs(particle.vx) < 0.1) {
            particle.vx = particle.originalVx;
        }
        if (Math.abs(particle.vy) < 0.1) {
            particle.vy = particle.originalVy;
        }

        // Bounce off edges
        if (particle.x < 0 || particle.x > this.canvas.width) {
            particle.vx = -particle.vx;
            particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
        }
        if (particle.y < 0 || particle.y > this.canvas.height) {
            particle.vy = -particle.vy;
            particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
        }
    }

    animate() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw mouse glow
        this.drawMouseGlow();

        // Calculate particle color based on typing
        let particleColor;
        if (this.isTyping && this.typingSpeed > 0.2) {
            const mix = this.typingSpeed;
            const r = Math.floor(this.colors.normal.r * (1 - mix) + this.colors.typing.r * mix);
            const g = Math.floor(this.colors.normal.g * (1 - mix) + this.colors.typing.g * mix);
            const b = Math.floor(this.colors.normal.b * (1 - mix) + this.colors.typing.b * mix);
            particleColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
        } else {
            particleColor = this.colors.particle;
        }

        // Update and draw particles
        for (let i = 0; i < this.particles.length; i++) {
            const p1 = this.particles[i];

            this.updateParticle(p1);
            this.drawParticle(p1, particleColor);

            // Draw connections to nearby particles
            for (let j = i + 1; j < this.particles.length; j++) {
                const p2 = this.particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const maxDistance = 120;

                if (distance < maxDistance) {
                    this.drawConnection(p1, p2, distance, maxDistance);
                }
            }
        }

        // Reset shadow for next frame
        this.ctx.shadowBlur = 0;

        // Continue animation
        this.animationId = requestAnimationFrame(() => this.animate());
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.neuralAnimation = new NeuralAnimation();
    });
} else {
    window.neuralAnimation = new NeuralAnimation();
}
