using Postgrest.Attributes;
using Postgrest.Models;
using System.Text.Json.Serialization;
using Supabase.Core.Attributes;

namespace Energy_Truth.Shared
{
    [Table("hourly_prices")]
    public class PriceDTO : BaseModel
    {
        [PrimaryKey("id", false)]
        public Guid Id { get; set; }

        [Column("provider_code")]
        public string ProviderCode { get; set; } = string.Empty;

        [Column("valid_from")]
        public DateTime ValidFrom { get; set; }

        [Column("price")]
        public decimal Price { get; set; }

        [Column("created_at")]
        public DateTime CreatedAt { get; set; }
    }
}
