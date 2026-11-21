/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04215(unsigned int count)
{
    const unsigned int limit = 200u;
    return count > limit ? limit : count;
}
