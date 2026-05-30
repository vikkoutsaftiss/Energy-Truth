using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;
using Energy_Truth.Shared.Repositories;


namespace Energy_Truth_WEB_API.Services.Customer
{
    public interface ICustomerService
    {
        Task<int> CreateCustomerAsync(CreateCustomerDTO customerDTO);
        Task<int> GetCustomerByEmailAsync(string email);
        Task<LoggedInUser> LoginCustomerAsync(LoginRequestDTO loginRequestDTO);
    }
}
