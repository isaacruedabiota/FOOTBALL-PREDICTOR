import "./globals.css";
import RegisterSW from "./RegisterSW";

export const metadata = {
  title: "Footy Predictor — Panel",
  description:
    "Predicciones de fútbol (modelo Dixon-Coles) y aciertos a lo largo de la temporada.",
  manifest: "/manifest.webmanifest",
  applicationName: "Footy Predictor",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Footy" },
  icons: {
    icon: [
      { url: "/favicon.png", sizes: "32x32", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: "/icon-192.png",
  },
};

export const viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f9f9f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        {children}
        <RegisterSW />
      </body>
    </html>
  );
}
