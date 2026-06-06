using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;
using BCrypt.Net;

namespace Energy_Truth_WEB_API.Services.Customer
{
    public class CustomerService : ICustomerService
    {
        private readonly ICustomerRepository _customerRepository;

        public CustomerService(ICustomerRepository customerRepository)
        {
            _customerRepository = customerRepository;
        }

        public async Task<int> CreateCustomerAsync(CreateCustomerDTO customerDTO)
        {
            var existingCustomer = await GetCustomerByEmailAsync(customerDTO.Email);
            if (existingCustomer != 0)
            {
                throw new InvalidOperationException("Dit e-mailadres is al geregistreerd.");
            }

            customerDTO.Password = BCrypt.Net.BCrypt.HashPassword(customerDTO.Password);

            var customer = await _customerRepository.CreateCustomerAsync(customerDTO);
            return customer;
        }

        public async Task<int> GetCustomerByEmailAsync(string email)
        {
            var customer = await _customerRepository.GetCustomerByEmailAsync(email);
            return customer;
        }

        public async Task<LoggedInUser> LoginCustomerAsync(LoginRequestDTO loginRequestDTO)
        {

            var customerAuth = await _customerRepository.GetCustomerAuthByEmailAsync(loginRequestDTO.Email);

            if (customerAuth == null) return null;

            // BCrypt kan nu veilig de hash controleren die uit de Shared DTO komt
            bool isPasswordValid = BCrypt.Net.BCrypt.Verify(loginRequestDTO.Password, customerAuth.PasswordHash);

            if (!isPasswordValid)
            {
                return null;
            }

            var customer = new LoggedInUser
                {
                    Id = customerAuth.Id,
                    Name = customerAuth.Name,
                    Email = customerAuth.Email,
                    IsLoggedIn = true,
                    IsAdmin = customerAuth.IsAdmin
            };

            return customer;
        }

        public async Task<bool> IsAdminAsync(int customerId)
        {
            return await _customerRepository.IsAdminAsync(customerId);
        }
    }
}
