using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;
using System.Text.Json.Serialization;

namespace Energy_Truth.Shared.DTO_s
{
    [NotMapped]
    public class CustomBatteryDTO
    {
        [JsonPropertyName("productnaam")]
        public string ProductName { get; set; }
        [JsonPropertyName("capaciteit_kwh")]
        public decimal CapacityKWh { get; set; }
        [JsonPropertyName("aanschafprijs_eur")]
        public decimal Price { get; set; }
        [JsonPropertyName("round_trip_efficiency")]
        public decimal? RoundTripEfficiency { get; set; }
        [JsonPropertyName("max_laden_kw")]
        public decimal? MaxChargePower { get; set; }
        [JsonPropertyName("max_ontladen_kw")]
        public decimal? MaxDischargePower { get; set; }
    }
}
