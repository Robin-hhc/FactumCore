/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04836(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}
