interface NominatimResult {
  lat: string
  lon: string
  display_name: string
}

export function useNominatim() {
  async function geocode(query: string): Promise<{ lat: number; lng: number } | null> {
    const results = await $fetch<NominatimResult[]>(
      'https://nominatim.openstreetmap.org/search',
      {
        params: { q: query, format: 'json', limit: 1, countrycodes: 'ph' },
        headers: {
          'Accept-Language': 'en-US',
          'User-Agent': 'SmartParkingApp/1.0 (contact@smartparking.ph)',
        },
      }
    )
    if (!results.length) return null
    return { lat: parseFloat(results[0].lat), lng: parseFloat(results[0].lon) }
  }

  return { geocode }
}
