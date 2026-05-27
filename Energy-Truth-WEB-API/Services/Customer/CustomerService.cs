using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.Customer
{
    public class CustomerService : ICustomerService
    {
        private readonly ICustomerRepository _customerRepository;

        public CustomerService(ICustomerRepository customerRepository)
        {
            _customerRepository = customerRepository;
        }

        public async Task<int> CreateOrGetCustomerAsync(CreateCustomerDTO customerDTO)
        {
            var existingCustomerId = await GetCustomerByEmailAsync(customerDTO.Email);
            if (existingCustomerId != 0)
            {
                return existingCustomerId;
            }

            var customerId = await _customerRepository.CreateCustomerAsync(customerDTO);
            return customerId;
        }

        public async Task<int> GetCustomerByEmailAsync(string email)
        {
            var customerId = await _customerRepository.GetCustomerByEmailAsync(email);
            return customerId;
        }
    }
}
