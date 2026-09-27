'use client';

export default function Footer() {
    const currentYear = new Date().getFullYear();

    return (
        <footer className="footer">
            <div className="footer__content">
                <div className="footer__logo">NEXARCH</div>

                <div className="footer__links">
                    <a href="#features" className="footer__link">Features</a>
                    <a href="#templates" className="footer__link">Templates</a>
                    <a href="#pricing" className="footer__link">Pricing</a>
                    <a href="#docs" className="footer__link">Docs</a>
                    <a href="#privacy" className="footer__link">Privacy</a>
                    <a href="#terms" className="footer__link">Terms</a>
                </div>

                <p className="footer__copyright">
                    © {currentYear} NEXARCH. Understand production architecture with confidence. All rights reserved.
                </p>
            </div>
        </footer>
    );
}
