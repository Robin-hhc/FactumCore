/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04649(unsigned int count)
{
    const unsigned int limit = 108u;
    return count > limit ? limit : count;
}
