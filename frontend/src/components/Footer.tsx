import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div>
          <p className="footer-brand">Campus Customs</p>
          <p>Officially licensed Yale apparel, printed and stitched down the block from campus since 1975.</p>
        </div>
        <div>
          <p className="footer-heading">Visit</p>
          <p>
            57 Broadway
            <br />
            New Haven, CT 06511
            <br />
            Open 7 days a week
          </p>
        </div>
        <div>
          <p className="footer-heading">Help</p>
          <p>
            <a href="mailto:orderdept@campuscustoms.com">orderdept@campuscustoms.com</a>
            <br />
            <a href="tel:+14753014205">(475) 301-4205</a>
            <br />
            30-day returns on unworn items
          </p>
        </div>
        <div>
          <p className="footer-heading">Shop</p>
          <p>
            <Link to="/products?category=hoodies">Hoodies</Link>
            <br />
            <Link to="/products?category=crewnecks">Crewnecks</Link>
            <br />
            <Link to="/products?category=tees">T-Shirts</Link>
            <br />
            <Link to="/about">Our story</Link>
          </p>
        </div>
      </div>
      <div className="footer-bottom">
        <p className="container">
          © Campus Customs class demo. Not affiliated with or endorsed by Campus Customs or Yale University. No real
          orders or payments.
        </p>
      </div>
    </footer>
  )
}
