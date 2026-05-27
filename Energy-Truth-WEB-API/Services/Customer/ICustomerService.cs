using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;


namespace Energy_Truth_WEB_API.Services.Customer
{
    public interface ICustomerService
    {
        Task<int> CreateOrGetCustomerAsync(CreateCustomerDTO customerDTO);
        Task<int> GetCustomerByEmailAsync(string email);
    }
}
