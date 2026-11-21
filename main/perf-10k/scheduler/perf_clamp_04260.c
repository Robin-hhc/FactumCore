/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04260(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
