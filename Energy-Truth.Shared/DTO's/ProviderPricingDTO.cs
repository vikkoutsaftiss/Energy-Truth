namespace Energy_Truth.Shared
{
    public class ProviderPricingDTO
    {
        public string ProviderName { get; set; }
        public string ProviderCode { get; set; }
        public decimal Price { get; set; }
        public DateTime ValidFrom { get; set; }
    }
}
