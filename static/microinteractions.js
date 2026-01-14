/**
 * Premium UX Micro-Interactions with GSAP SVGator-Style Morphing
 * Advanced animations and effects
 */

// ===== GSAP SVG MORPHING LOADER =====
let currentMorphPhase = 0;
let svgContainer = null;

function initSVGMorphing() {
    svgContainer = document.getElementById('morph-svg-container');
    if (!svgContainer) {
        console.warn('SVG morph container not found');
        return;
    }
}

function updateMorphingLoader(progress, message) {
    if (!svgContainer || typeof gsap === 'undefined') return;

    let targetPhase = 0;
    if (progress < 40) targetPhase = 0; // Cloud
    else if (progress < 60) targetPhase = 1; // Waveform
    else if (progress < 95) targetPhase = 2; // Brain
    else targetPhase = 3; // Checkmark

    if (targetPhase !== currentMorphPhase) {
        morphToPhase(targetPhase);
        currentMorphPhase = targetPhase;
    }
}

function morphToPhase(phase) {
    const svgElement = svgContainer.querySelector('svg');
    if (!svgElement || typeof gsap === 'undefined') return;

    gsap.to(svgElement, {
        opacity: 0,
        scale: 0.8,
        duration: 0.3,
        onComplete: () => {
            const svgs = [getCloudSVG(), getWaveformSVG(), getBrainSVG(), getCheckmarkSVG()];
            svgElement.innerHTML = svgs[phase] || svgs[0];

            const animFns = [animateCloudFill, animateWaveform, animateBrain, animateCheckmark];
            if (animFns[phase]) animFns[phase]();

            gsap.fromTo(svgElement,
                { opacity: 0, scale: 0.8 },
                { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.7)' }
            );
        }
    });
}

function getCloudSVG() {
    return `<path id="cloud-outline" d="M50 30 Q40 20, 50 10 Q70 10, 80 20 Q90 25, 90 35 Q85 45, 75 45 L25 45 Q15 45, 15 35 Q15 25, 25 25" fill="none" stroke="#667eea" stroke-width="2"/><path id="cloud-fill" d="M50 30 Q40 20, 50 10 Q70 10, 80 20 Q90 25, 90 35 Q85 45, 75 45 L25 45 Q15 45, 15 35 Q15 25, 25 25" fill="#667eea" opacity="0.3" style="clip-path: inset(100% 0 0 0);"/>`;
}

function getWaveformSVG() {
    let svg = '';
    for (let i = 1; i <= 9; i++) {
        const x = i * 10;
        svg += `<line id="wave${i}" x1="${x}" y1="25" x2="${x}" y2="35" stroke="#8b5cf6" stroke-width="3" stroke-linecap="round"/>`;
    }
    return svg;
}

function getBrainSVG() {
    return `<circle id="brain-center" cx="50" cy="30" r="15" fill="none" stroke="#ec4899" stroke-width="2"/><path d="M35 25 L20 15" stroke="#ec4899" stroke-width="1.5"/><path d="M65 25 L80 15" stroke="#ec4899" stroke-width="1.5"/><path d="M35 35 L20 45" stroke="#ec4899" stroke-width="1.5"/><path d="M65 35 L80 45" stroke="#ec4899" stroke-width="1.5"/><circle cx="20" cy="15" r="3" fill="#ec4899"/><circle cx="80" cy="15" r="3" fill="#ec4899"/><circle cx="20" cy="45" r="3" fill="#ec4899"/><circle cx="80" cy="45" r="3" fill="#ec4899"/><circle id="glow-circle" cx="50" cy="30" r="20" fill="#ec4899" opacity="0"/>`;
}

function getCheckmarkSVG() {
    return `<circle id="check-circle" cx="50" cy="30" r="20" fill="none" stroke="#10b981" stroke-width="3"/><path id="check-path" d="M35 30 L45 40 L65 20" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="100" stroke-dashoffset="100"/>`;
}

function animateCloudFill() {
    const fill = document.getElementById('cloud-fill');
    if (fill && typeof gsap !== 'undefined') {
        gsap.to(fill, { clipPath: 'inset(0% 0 0 0)', duration: 2, ease: 'power1.inOut', repeat: -1, yoyo: true });
    }
}

function animateWaveform() {
    if (typeof gsap === 'undefined') return;
    for (let i = 1; i <= 9; i++) {
        const wave = document.getElementById(`wave${i}`);
        if (wave) {
            gsap.to(wave, {
                attr: { y1: `${25 - Math.random() * 15}`, y2: `${35 + Math.random() * 15}` },
                duration: 0.3 + Math.random() * 0.3,
                ease: 'power1.inOut',
                repeat: -1,
                yoyo: true,
                delay: i * 0.05
            });
        }
    }
}

function animateBrain() {
    if (typeof gsap === 'undefined') return;
    gsap.to('#brain-center', { attr: { r: 18 }, duration: 0.8, ease: 'power1.inOut', repeat: -1, yoyo: true });
    gsap.to('#glow-circle', { opacity: 0.3, attr: { r: 25 }, duration: 1.5, ease: 'power1.out', repeat: -1 });
}

function animateCheckmark() {
    if (typeof gsap === 'undefined') return;
    const circle = document.getElementById('check-circle');
    const path = document.getElementById('check-path');
    if (circle) gsap.from(circle, { attr: { r: 0 }, duration: 0.6, ease: 'elastic.out(1, 0.5)' });
    if (path) gsap.to(path, { strokeDashoffset: 0, duration: 0.8, ease: 'power2.out', delay: 0.3 });
    gsap.to('#checkmark-group', { scale: 1.1, duration: 0.3, ease: 'power2.out', delay: 1, yoyo: true, repeat: 2 });
}

// ===== MAGNETIC BUTTONS =====
function initMagneticButtons() {
    if (typeof gsap === 'undefined') return;

    const buttons = document.querySelectorAll('button, a[class*="btn"]');
    buttons.forEach(button => {
        button.style.transition = 'none';

        button.addEventListener('mouseenter', function () {
            gsap.to(this, { scale: 1.05, duration: 0.3, ease: 'power2.out' });
        });

        button.addEventListener('mouseleave', function () {
            gsap.to(this, { x: 0, y: 0, scale: 1, duration: 0.5, ease: 'elastic.out(1, 0.5)' });
        });

        button.addEventListener('mousemove', function (e) {
            const rect = this.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const deltaX = (e.clientX - centerX) * 0.3;
            const deltaY = (e.clientY - centerY) * 0.3;
            gsap.to(this, { x: deltaX, y: deltaY, duration: 0.3, ease: 'power2.out' });
        });
    });
}

// ===== STAGGERED REVEAL WITH GSAP =====
function staggerRevealGSAP(elements, options = {}) {
    if (typeof gsap === 'undefined') return;

    const defaults = { duration: 0.6, stagger: 0.1, ease: 'power2.out', y: 30, opacity: 0 };
    const settings = { ...defaults, ...options };

    gsap.from(elements, {
        y: settings.y,
        opacity: settings.opacity,
        duration: settings.duration,
        stagger: settings.stagger,
        ease: settings.ease
    });
}

// ===== 3D TILT CARD EFFECT (Apple TV Style) =====
class TiltCard {
    constructor(element) {
        this.element = element;
        this.bounds = null;
        this.init();
    }

    init() {
        this.element.classList.add('tilt-card');

        this.element.addEventListener('mouseenter', () => this.handleMouseEnter());
        this.element.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.element.addEventListener('mouseleave', () => this.handleMouseLeave());
    }

    handleMouseEnter() {
        this.bounds = this.element.getBoundingClientRect();
        this.element.classList.add('tilting');
    }

    handleMouseMove(e) {
        if (!this.bounds) return;

        const mouseX = e.clientX;
        const mouseY = e.clientY;

        const leftX = mouseX - this.bounds.left;
        const topY = mouseY - this.bounds.top;

        const centerX = leftX - this.bounds.width / 2;
        const centerY = topY - this.bounds.height / 2;

        const percentX = centerX / (this.bounds.width / 2);
        const percentY = centerY / (this.bounds.height / 2);

        // Calculate tilt (subtle angles)
        const rotateY = percentX * 5; // Max 5 degrees
        const rotateX = -percentY * 5;

        // Apply transform
        this.element.style.transform = `
            perspective(1000px)
            rotateX(${rotateX}deg)
            rotateY(${rotateY}deg)
            scale3d(1.02, 1.02, 1.02)
        `;

        // Calculate light reflection position (opposite to mouse)
        const reflectX = 50 + (percentX * 30);
        const reflectY = 50 + (percentY * 30);

        // Update sheen gradient
        if (this.element.querySelector) {
            const before = window.getComputedStyle(this.element, '::before');
            this.element.style.setProperty('--sheen-x', `${reflectX}%`);
            this.element.style.setProperty('--sheen-y', `${reflectY}%`);
        }

        // Update ::before pseudo-element via CSS variable
        const sheenBg = `radial-gradient(circle at ${reflectX}% ${reflectY}%, rgba(255, 255, 255, 0.15) 0%, transparent 60%)`;
        this.element.style.setProperty('--sheen-bg', sheenBg);
    }

    handleMouseLeave() {
        this.element.classList.remove('tilting');
        this.element.style.transform = '';
        this.bounds = null;
    }
}

// ===== LIQUID STATE TRANSITIONS =====
function liquidButtonMorph(buttonId, targetSectionId) {
    const button = document.getElementById(buttonId);
    const targetSection = document.getElementById(targetSectionId);

    if (!button || !targetSection) return;

    // Get button position and size
    const buttonRect = button.getBoundingClientRect();

    // Add morphing class
    button.classList.add('morphing', 'liquid-expand');

    // After morph animation, hide input section and show progress
    setTimeout(() => {
        // Smoothly hide current section
        const inputSections = document.querySelectorAll('[id^="input-section"]');
        inputSections.forEach(section => {
            section.style.opacity = '0';
            section.style.transform = 'scale(0.95)';
            section.style.transition = 'all 0.3s ease';
        });

        setTimeout(() => {
            inputSections.forEach(section => section.classList.add('hidden'));
            targetSection.classList.remove('hidden');

            // Reveal target section with animation
            targetSection.style.opacity = '0';
            targetSection.style.transform = 'scale(0.95)';

            requestAnimationFrame(() => {
                targetSection.style.transition = 'all 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
                targetSection.style.opacity = '1';
                targetSection.style.transform = 'scale(1)';
            });
        }, 300);
    }, 600);
}

// ===== STAGGERED CONTENT REVEAL =====
function staggeredReveal(containerSelector, itemSelector = 'p, div, li') {
    const container = typeof containerSelector === 'string'
        ? document.querySelector(containerSelector)
        : containerSelector;

    if (!container) return;

    const items = container.querySelectorAll(itemSelector);

    items.forEach((item, index) => {
        // Add reveal class and delay
        item.classList.add('reveal-item-rtl');
        item.classList.add(`reveal-delay-${Math.min(index + 1, 10)}`);
    });
}

// Split text into paragraphs for staggered reveal
function splitTextForReveal(textElement) {
    if (!textElement) return;

    const text = textElement.textContent;
    const paragraphs = text.split('\n\n').filter(p => p.trim());

    // Clear and rebuild with animated paragraphs
    textElement.innerHTML = '';

    paragraphs.forEach((para, index) => {
        const p = document.createElement('p');
        p.textContent = para;
        p.classList.add('reveal-item-rtl', `reveal-delay-${Math.min(index + 1, 10)}`);
        p.style.marginBottom = '1rem';
        textElement.appendChild(p);
    });
}

// ===== ENHANCED COMPLETION WITH STAGGERED REVEAL =====
function showCompletionWithReveal(taskId) {
    // Hide progress section
    document.getElementById('progress-section').classList.add('hidden');

    const completionSection = document.getElementById('completion-section');
    completionSection.classList.remove('hidden');

    // Stagger reveal of completion elements
    const completionItems = completionSection.querySelectorAll('.reveal-target');
    completionItems.forEach((item, index) => {
        item.classList.add('reveal-item', `reveal-delay-${index + 1}`);
    });

    // Update links
    const downloadLink = document.getElementById('download-link');
    const chatLink = document.getElementById('chat-link');

    if (downloadLink) downloadLink.href = `/download/${taskId}`;
    if (chatLink) chatLink.href = `/player/${taskId}`;
}

// ===== INITIALIZE TILT CARDS =====
function initializeTiltCards() {
    const cards = document.querySelectorAll('.card, .bg-white.rounded-2xl');
    cards.forEach(card => {
        new TiltCard(card);
    });
}

// ===== RIPPLE EFFECT ON BUTTONS =====
function addRippleEffect(button) {
    if (!button) return;

    button.classList.add('ripple');

    button.addEventListener('click', function (e) {
        // Ripple is handled by CSS
        // Optional: Add custom ripple logic here
    });
}

// ===== AUTO-INITIALIZE ON PAGE LOAD =====
document.addEventListener('DOMContentLoaded', () => {
    // Initialize GSAP features
    initSVGMorphing();
    initMagneticButtons();

    // Initialize 3D tilt cards
    initializeTiltCards();

    // Add ripple to all buttons
    const buttons = document.querySelectorAll('button, .btn');
    buttons.forEach(btn => addRippleEffect(btn));

    // Add pulse effect to primary buttons
    const primaryButtons = document.querySelectorAll('[id$="-btn"]');
    primaryButtons.forEach(btn => btn.classList.add('btn-pulse'));

    console.log('🎨 GSAP Micro-interactions initialized!');
});

// Export for use in other scripts
window.TiltCard = TiltCard;
window.liquidButtonMorph = liquidButtonMorph;
window.staggeredReveal = staggeredReveal;
window.splitTextForReveal = splitTextForReveal;
window.showCompletionWithReveal = showCompletionWithReveal;
window.updateMorphingLoader = updateMorphingLoader;
window.morphToPhase = morphToPhase;
window.staggerRevealGSAP = staggerRevealGSAP;
