using Supabase.Postgrest.Models; // De nieuwe plek voor BaseModel
using Supabase.Postgrest.Attributes;

namespace Energy_Truth.Shared;

[Table("providers")]
public class ProviderDTO : BaseModel
{
    public Guid Id { get; set; }

    public string Code { get; set; }

    public string Name { get; set; }

    public DateTime CreatedAt { get; set; }
}
