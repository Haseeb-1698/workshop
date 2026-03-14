/**
 * Contact component
 *
 * Displays a contact form so visitors can send you a message.
 * Uses mailto: link to send the message via the visitor's email client.
 */

import React, { useState } from "react";
import PropTypes from "prop-types";

const Contact = ({ email, primaryColor, secondaryColor }) => {
  const [formData, setFormData] = useState({
    senderName: "",
    senderEmail: "",
    message: "",
  });

  const handleChange = (e) => {
    const { name: fieldName, value } = e.target;
    setFormData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const subject = encodeURIComponent(`Message from ${formData.senderName}`);
    const body = encodeURIComponent(
      `Name: ${formData.senderName}\nEmail: ${formData.senderEmail}\n\nMessage:\n${formData.message}`
    );
    window.open(`mailto:${email}?subject=${subject}&body=${body}`);
  };

  return (
    <section className="padding" id="contact">
      <div
        style={{
          backgroundColor: secondaryColor,
          width: "min(50%, 600px)",
          minWidth: "280px",
          padding: "4rem",
          margin: "0 auto",
          textAlign: "center",
          borderRadius: "12px",
          boxSizing: "border-box",
        }}
      >
        <h2>Get In Touch</h2>
        <p className="large" style={{ marginBottom: "2rem" }}>
          Have a project in mind? I&apos;d love to hear from you.
        </p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input
            type="text"
            name="senderName"
            placeholder="Your Name"
            value={formData.senderName}
            onChange={handleChange}
            required
            style={inputStyle}
          />
          <input
            type="email"
            name="senderEmail"
            placeholder="Your Email"
            value={formData.senderEmail}
            onChange={handleChange}
            required
            style={inputStyle}
          />
          <textarea
            name="message"
            placeholder="Your Message"
            value={formData.message}
            onChange={handleChange}
            required
            rows={6}
            style={{ ...inputStyle, resize: "vertical" }}
          />
          <button
            type="submit"
            style={{
              backgroundColor: primaryColor,
              color: "white",
              border: "none",
              borderRadius: "8px",
              padding: "0.85rem 2rem",
              fontSize: "1rem",
              cursor: "pointer",
              fontFamily: "inherit",
              fontWeight: 600,
              marginTop: "0.5rem",
            }}
          >
            Send Message
          </button>
        </form>
      </div>
    </section>
  );
};

const inputStyle = {
  border: "1px solid #ccc",
  borderRadius: "8px",
  fontFamily: "inherit",
  fontSize: "1rem",
  padding: "0.75rem 1rem",
  width: "100%",
  boxSizing: "border-box",
};

Contact.defaultProps = {
  email: "",
  primaryColor: "#4E567E",
  secondaryColor: "#D2F1E4",
};

Contact.propTypes = {
  email: PropTypes.string,
  primaryColor: PropTypes.string,
  secondaryColor: PropTypes.string,
};

export default Contact;
