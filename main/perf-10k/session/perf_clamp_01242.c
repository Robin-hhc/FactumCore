/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01242(unsigned int count)
{
    const unsigned int limit = 206u;
    return count > limit ? limit : count;
}
