/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04154(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
